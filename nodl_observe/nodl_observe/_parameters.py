# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Remote parameter collection via the target node's ``~/...parameter`` services.

This is the only part of observation that *talks to* the target node rather
than the graph cache.  It must degrade gracefully: an unresponsive or
parameter-less target yields empty arrays plus a logged warning, never a hard
failure.  The async future plumbing lives here; the value-shaping helpers
(:func:`build_parameters`) are pure so they can be unit-tested without a node.
"""

import time

import rclpy
from rcl_interfaces.srv import DescribeParameters, GetParameters, ListParameters


def _service_name(target_fqn: str, suffix: str) -> str:
    """Build a fully-qualified parameter service name for the target node.

    The six parameter services live under the node's FQN, e.g.
    ``/ns/node`` -> ``/ns/node/list_parameters``.
    """
    return target_fqn.rstrip('/') + '/' + suffix


def _call(node, client, request, deadline):
    """Call a service client and return the response, or ``None`` on failure.

    Bounded by the *shared* ``deadline`` (``time.monotonic()`` based), so the
    timeout is a ceiling across all parameter round-trips rather than a
    per-call allowance.  Spins the caller-provided node until the future
    completes.  Any timeout / unavailable-service condition returns ``None`` so
    the caller can degrade gracefully.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        return None
    if not client.service_is_ready() and not client.wait_for_service(timeout_sec=remaining):
        return None
    future = client.call_async(request)
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        future.cancel()
        return None
    rclpy.spin_until_future_complete(node, future, timeout_sec=remaining)
    if not future.done():
        future.cancel()
        return None
    return future.result()


def collect_parameters(node, target_fqn: str, timeout_sec: float):
    """Collect parameter descriptors and current values from the target node.

    Returns ``(descriptors, values)`` -- two parallel, equal-length lists --
    or ``([], [])`` if the target is unresponsive / exposes no parameters.
    ``timeout_sec`` is a shared ceiling across all three service round-trips,
    not a per-call allowance.  Emits a warning through ``node.get_logger()``
    on degradation rather than raising -- including when the target dies
    mid-observation and a service handle raises underneath us.
    """
    logger = node.get_logger()
    deadline = time.monotonic() + timeout_sec
    list_client = node.create_client(
        ListParameters, _service_name(target_fqn, 'list_parameters'))
    describe_client = node.create_client(
        DescribeParameters, _service_name(target_fqn, 'describe_parameters'))
    get_client = node.create_client(
        GetParameters, _service_name(target_fqn, 'get_parameters'))
    try:
        list_resp = _call(node, list_client, ListParameters.Request(), deadline)
        if list_resp is None:
            logger.warning(
                f"Could not reach parameter services on '{target_fqn}'; "
                'reporting empty parameters.')
            return [], []

        names = list(list_resp.result.names)
        if not names:
            return [], []

        describe_resp = _call(
            node, describe_client, DescribeParameters.Request(names=names), deadline)
        get_resp = _call(
            node, get_client, GetParameters.Request(names=names), deadline)

        if describe_resp is None or get_resp is None:
            logger.warning(
                f"Listed parameters on '{target_fqn}' but could not describe or "
                'read them; reporting empty parameters.')
            return [], []

        return build_parameters(
            names, list(describe_resp.descriptors), list(get_resp.values))
    except Exception as e:
        # Graceful-degradation contract: a target that dies or tears its
        # parameter services down mid-observation (InvalidHandle, RCLError,
        # ...) must degrade to empty arrays, never fail the observation.
        logger.warning(
            f"Parameter collection on '{target_fqn}' failed "
            f'({type(e).__name__}: {e}); reporting empty parameters.')
        return [], []
    finally:
        node.destroy_client(list_client)
        node.destroy_client(describe_client)
        node.destroy_client(get_client)


def build_parameters(names, descriptors, values):
    """Pair descriptors with values into two parallel, sorted lists.

    Pure: takes the listed names plus the ``describe``/``get`` responses and
    returns ``(descriptors, values)`` sorted by name and matched 1:1.  Robust
    to length mismatches between the three responses (which can happen if a
    parameter is removed mid-observation) -- only names present in *both*
    descriptors and values are kept.
    """
    desc_by_name = {d.name: d for d in descriptors}
    # GetParameters responses are positional (no name field), aligned to the
    # request order, which mirrors the listed names.
    value_by_name = {}
    for name, value in zip(names, values):
        value_by_name[name] = value

    paired = []
    for name in names:
        descriptor = desc_by_name.get(name)
        value = value_by_name.get(name)
        if descriptor is None or value is None:
            continue
        paired.append((name, descriptor, value))

    paired.sort(key=lambda item: item[0])
    out_descriptors = [descriptor for _, descriptor, _ in paired]
    out_values = [value for _, _, value in paired]
    return out_descriptors, out_values
