# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Pure mapping from :mod:`rclpy.qos` to ``rosgraph_msgs/QoSProfile``.

Kept free of any graph access so it can be unit-tested in isolation.  The
:func:`qos_to_msg` mapper is the one place QoS enums are translated; per the
``QoSProfile.msg`` comment, an *observed* policy can never legitimately be
``SYSTEM_DEFAULT`` or ``BEST_AVAILABLE`` -- those are request-time placeholders
that the middleware resolves to a concrete policy.  Seeing one in output
therefore signals a mapping bug, which the unit tests assert against.
"""

from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    LivelinessPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rosgraph_msgs.msg import QoSProfile as QoSProfileMsg


# The integer values of the rclpy policy enums are defined to match the
# ``*_<POLICY>`` constants in ``QoSProfile.msg`` one-to-one (both derive from
# the same rmw enum).  We still map explicitly rather than assigning the raw
# enum value, so that an upstream divergence surfaces as a KeyError here (a
# loud, testable failure) instead of a silently wrong byte in the output.
_HISTORY = {
    HistoryPolicy.SYSTEM_DEFAULT: QoSProfileMsg.HISTORY_SYSTEM_DEFAULT,
    HistoryPolicy.KEEP_LAST: QoSProfileMsg.HISTORY_KEEP_LAST,
    HistoryPolicy.KEEP_ALL: QoSProfileMsg.HISTORY_KEEP_ALL,
    HistoryPolicy.UNKNOWN: QoSProfileMsg.HISTORY_UNKNOWN,
}
_RELIABILITY = {
    ReliabilityPolicy.SYSTEM_DEFAULT: QoSProfileMsg.RELIABILITY_SYSTEM_DEFAULT,
    ReliabilityPolicy.RELIABLE: QoSProfileMsg.RELIABILITY_RELIABLE,
    ReliabilityPolicy.BEST_EFFORT: QoSProfileMsg.RELIABILITY_BEST_EFFORT,
    ReliabilityPolicy.UNKNOWN: QoSProfileMsg.RELIABILITY_UNKNOWN,
}
_DURABILITY = {
    DurabilityPolicy.SYSTEM_DEFAULT: QoSProfileMsg.DURABILITY_SYSTEM_DEFAULT,
    DurabilityPolicy.TRANSIENT_LOCAL: QoSProfileMsg.DURABILITY_TRANSIENT_LOCAL,
    DurabilityPolicy.VOLATILE: QoSProfileMsg.DURABILITY_VOLATILE,
    DurabilityPolicy.UNKNOWN: QoSProfileMsg.DURABILITY_UNKNOWN,
}
_LIVELINESS = {
    LivelinessPolicy.SYSTEM_DEFAULT: QoSProfileMsg.LIVELINESS_SYSTEM_DEFAULT,
    LivelinessPolicy.AUTOMATIC: QoSProfileMsg.LIVELINESS_AUTOMATIC,
    LivelinessPolicy.MANUAL_BY_TOPIC: QoSProfileMsg.LIVELINESS_MANUAL_BY_TOPIC,
    LivelinessPolicy.UNKNOWN: QoSProfileMsg.LIVELINESS_UNKNOWN,
}

# ``BEST_AVAILABLE`` is a request-time policy added in Iron; it does not exist
# in Humble's ``rclpy.qos`` enums.  It can never be an *observed* value, so we
# add it only where the running rclpy defines it -- keeping the package
# importable on Humble while still mapping it on Iron+ if it ever appears.
for _enum, _table, _const in (
    (ReliabilityPolicy, _RELIABILITY, 'RELIABILITY_BEST_AVAILABLE'),
    (DurabilityPolicy, _DURABILITY, 'DURABILITY_BEST_AVAILABLE'),
    (LivelinessPolicy, _LIVELINESS, 'LIVELINESS_BEST_AVAILABLE'),
):
    if hasattr(_enum, 'BEST_AVAILABLE'):
        _table[_enum.BEST_AVAILABLE] = getattr(QoSProfileMsg, _const)


def qos_to_msg(qos: QoSProfile) -> QoSProfileMsg:
    """Translate an :class:`rclpy.qos.QoSProfile` into a ``QoSProfile`` message.

    :raises KeyError: if an rclpy policy has no ``QoSProfile.msg`` counterpart,
        which would mean the two enum definitions have drifted apart.
    """
    msg = QoSProfileMsg()
    msg.depth = qos.depth
    msg.history = _HISTORY[HistoryPolicy(qos.history)]
    msg.reliability = _RELIABILITY[ReliabilityPolicy(qos.reliability)]
    msg.durability = _DURABILITY[DurabilityPolicy(qos.durability)]
    msg.liveliness = _LIVELINESS[LivelinessPolicy(qos.liveliness)]
    msg.deadline = qos.deadline.to_msg()
    msg.lifespan = qos.lifespan.to_msg()
    msg.liveliness_lease_duration = qos.liveliness_lease_duration.to_msg()
    return msg


def latched_qos() -> QoSProfile:
    """The QoS profile of the latched observation publish.

    ``reliable`` + ``transient_local`` + ``keep_last(1)`` -- the contract for
    ``/nodl/observed_node`` from the plan.  Lives here (not in the CLI verb) so
    publishers and subscribers of the latched topic share a single definition.
    """
    return QoSProfile(
        depth=1,
        history=HistoryPolicy.KEEP_LAST,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )


def unknown_qos_msg() -> QoSProfileMsg:
    """Return a ``QoSProfile`` message whose policies are all ``*_UNKNOWN``.

    Used for service / action-service endpoints, whose actual QoS is not
    observable from rclpy (there is no ``get_*_info_by_service`` API).  Per the
    plan, honest-unknown beats plausible-wrong; Describe (#53) decides what
    UNKNOWN maps to in NoDL.  Durations are left at zero -- they too are
    unobserved -- and ``depth`` stays 0.
    """
    msg = QoSProfileMsg()
    msg.history = QoSProfileMsg.HISTORY_UNKNOWN
    msg.reliability = QoSProfileMsg.RELIABILITY_UNKNOWN
    msg.durability = QoSProfileMsg.DURABILITY_UNKNOWN
    msg.liveliness = QoSProfileMsg.LIVELINESS_UNKNOWN
    return msg
