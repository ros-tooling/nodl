# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Pure builders turning raw graph-query results into ``Node`` sub-messages.

Nothing in here touches the ROS graph: every function takes already-collected
plain data (names-and-types lists, ``TopicEndpointInfo`` objects) and returns
filled messages.  That keeps the whole endpoint-collection layer unit-testable
without an executor -- tests hand-roll fixtures and assert exact message
contents.
"""

from rosgraph_msgs.msg import Action, InterfaceType, Service, Topic, TypeHash

from ._qos import qos_to_msg, unknown_qos_msg


# Constituent suffixes of a hidden ``<action>/_action/*`` entity, by kind.
_ACTION_SERVICE_SUFFIXES = ('send_goal', 'get_result', 'cancel_goal')
_ACTION_TOPIC_SUFFIXES = ('feedback', 'status')
_ACTION_INFIX = '/_action/'


def _type_hash_msg(source_hash) -> TypeHash:
    """Copy an rclpy ``TypeHash`` into a ``rosgraph_msgs/TypeHash`` message.

    ``source_hash`` is the ``topic_type_hash`` attribute of a
    ``TopicEndpointInfo`` (version + 32-byte value).  An unset/unsupported hash
    comes back as version ``-1``; we clamp that to the message default (``0``)
    rather than overflowing the ``uint8`` field.
    """
    msg = TypeHash()
    version = getattr(source_hash, 'version', 0)
    msg.version = version if 0 <= version <= 255 else 0
    value = bytes(getattr(source_hash, 'value', b''))
    # The message field is a fixed-size uint8[32]; assign element-wise so a
    # short/long source is handled gracefully.
    for i in range(min(len(value), 32)):
        msg.value[i] = value[i]
    return msg


def _interface_type(type_name: str, source_hash=None) -> InterfaceType:
    """Build an ``InterfaceType`` from a type name and optional type hash."""
    iface = InterfaceType()
    iface.name = type_name
    if source_hash is not None:
        iface.hash = _type_hash_msg(source_hash)
    return iface


def build_topic(name: str, endpoint_info) -> Topic:
    """Build a ``Topic`` (publisher or subscription) from a ``TopicEndpointInfo``.

    The endpoint info carries the observed QoS and, on Iron+ (REP-2011), the
    RIHS type hash.  Older distros (Humble) have no ``topic_type_hash`` on
    ``TopicEndpointInfo`` -- there the hash is simply left unset rather than
    fabricated, the same honest-unknown treatment service type hashes get.
    """
    topic = Topic()
    topic.name = name
    topic.type = _interface_type(
        endpoint_info.topic_type, getattr(endpoint_info, 'topic_type_hash', None))
    topic.qos = qos_to_msg(endpoint_info.qos_profile)
    return topic


def build_service(name: str, request_type: str, response_type: str) -> Service:
    """Build a ``Service`` with UNKNOWN QoS and no type hash.

    Per-direction service QoS is not observable from rclpy and the service type
    hash is likewise unavailable, so both are left at their honest-unknown
    defaults (see :func:`nodl_observe._qos.unknown_qos_msg`).
    """
    service = Service()
    service.name = name
    service.request_type = _interface_type(request_type)
    service.response_type = _interface_type(response_type)
    service.request_qos = unknown_qos_msg()
    service.response_qos = unknown_qos_msg()
    return service


def _split_service_type(types) -> tuple:
    """Return ``(request_type, response_type)`` for a service/action endpoint.

    Graph queries report a single service type string (e.g.
    ``example_interfaces/srv/AddTwoInts``).  ``Service.msg`` splits this into a
    request and response ``InterfaceType``; both carry the same service type
    name, with the request/response distinction implicit in the field.  If
    multiple types are reported (a name collision), the first is used.
    """
    type_name = types[0] if types else ''
    return type_name, type_name


def build_topic_endpoints(names_and_types, infos_by_topic) -> list:
    """Build a sorted list of ``Topic`` messages for one endpoint direction.

    :param names_and_types: iterable of ``(topic_name, [type, ...])`` for the
        target node, as returned by ``get_*_names_and_types_by_node``.
    :param infos_by_topic: mapping ``topic_name -> [TopicEndpointInfo, ...]``
        already filtered to this node's endpoints on that topic.  When a topic
        has multiple matching endpoints (one per declared type), each becomes
        its own ``Topic`` entry.
    """
    topics = []
    for name, types in names_and_types:
        infos = infos_by_topic.get(name, [])
        if infos:
            for info in infos:
                topics.append(build_topic(name, info))
        else:
            # No introspection info came back for this endpoint (e.g. the RMW
            # could not report it).  Emit a name/type-only entry rather than
            # dropping the endpoint; QoS and hash stay at message defaults.
            for type_name in types:
                topic = Topic()
                topic.name = name
                topic.type = _interface_type(type_name)
                topics.append(topic)
    return _sorted_topics(topics)


def build_service_endpoints(names_and_types) -> list:
    """Build a sorted list of ``Service`` messages from names-and-types."""
    services = []
    for name, types in names_and_types:
        request_type, response_type = _split_service_type(types)
        services.append(build_service(name, request_type, response_type))
    return _sorted_services(services)


def _action_constituent_names(action_name: str) -> dict:
    """Map each ``_action/*`` constituent name to its role for one action."""
    base = action_name + _ACTION_INFIX
    names = {base + suffix: ('service', suffix) for suffix in _ACTION_SERVICE_SUFFIXES}
    names.update({base + suffix: ('topic', suffix) for suffix in _ACTION_TOPIC_SUFFIXES})
    return names


def fold_actions(
    action_names_and_types,
    service_endpoints,
    topic_endpoints,
):
    """Fold hidden ``_action/*`` constituents into ``Action`` messages.

    :param action_names_and_types: ``(action_name, [type, ...])`` from
        ``rclpy.action.graph`` for one direction (servers or clients).
    :param service_endpoints: list of already-built ``Service`` messages (this
        node's flat services); constituents are removed from it in place.
    :param topic_endpoints: list of already-built ``Topic`` messages for the
        matching topic direction; constituents removed in place.
    :returns: a sorted list of ``Action`` messages.

    Constituents matched to a parent action are *moved* out of the flat lists
    (representation mandated by the schema, not interpretation).  An
    ``_action/*`` entity whose parent action is absent from the action graph is
    left flat -- never silently discarded (the folding rule).
    """
    services_by_name = {s.name: s for s in service_endpoints}
    topics_by_name = {t.name: t for t in topic_endpoints}

    actions = []
    consumed_services = set()
    consumed_topics = set()

    for action_name, types in action_names_and_types:
        action = Action()
        action.name = action_name
        type_name = types[0] if types else ''
        for const_name, (kind, suffix) in _action_constituent_names(action_name).items():
            if kind == 'service':
                service = services_by_name.get(const_name)
                if service is not None:
                    consumed_services.add(const_name)
                else:
                    # Constituent not present in the graph for this node; build
                    # a placeholder so the Action message stays well-formed.
                    service = build_service(const_name, type_name, type_name)
                setattr(action, suffix, service)
            else:
                topic = topics_by_name.get(const_name)
                if topic is None:
                    topic = Topic()
                    topic.name = const_name
                    topic.type = _interface_type(type_name)
                else:
                    consumed_topics.add(const_name)
                setattr(action, suffix, topic)
        actions.append(action)

    # Remove folded constituents from the flat lists, in place.
    service_endpoints[:] = [s for s in service_endpoints if s.name not in consumed_services]
    topic_endpoints[:] = [t for t in topic_endpoints if t.name not in consumed_topics]

    return _sorted_actions(actions)


def _sorted_topics(topics) -> list:
    return sorted(topics, key=lambda t: (t.name, t.type.name))


def _sorted_services(services) -> list:
    return sorted(services, key=lambda s: (s.name, s.request_type.name))


def _sorted_actions(actions) -> list:
    return sorted(actions, key=lambda a: (a.name, a.send_goal.request_type.name))
