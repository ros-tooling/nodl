# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Live smoke check (NOT part of the unit suite).

Proves, in the Jazzy container under the pinned RMW, that:
  1. ``TopicEndpointInfo.topic_type_hash`` is actually populated (non-zero RIHS
     hash) -- a plan deliverable to verify before the PR claims it.
  2. ``observe_node`` end-to-end returns a sane ``Node`` message for a real node.

Run with a spinning executor on a background thread so parameter futures and
discovery progress.  This is intentionally outside pytest (it needs a live
graph) and is invoked directly by the smoke step.
"""

import threading

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

from example_interfaces.action import Fibonacci
from rclpy.action import ActionServer
from std_msgs.msg import String
from example_interfaces.srv import AddTwoInts

from nodl_observe import observe_node
from nodl_observe.serialization import to_yaml


def main():
    rclpy.init()
    target = Node('smoke_target', namespace='/demo')
    target.declare_parameter('speed', 1.5)
    target.create_publisher(String, 'chatter', 10)
    target.create_subscription(String, 'commands', lambda m: None, 10)
    target.create_service(AddTwoInts, 'add', lambda req, resp: resp)
    ActionServer(target, Fibonacci, 'fibonacci', lambda goal: goal)

    observer = Node('smoke_observer')

    # Spin the target so its parameter services respond; spin the observer so
    # observe_node's own parameter futures complete.
    executor = SingleThreadedExecutor()
    executor.add_node(target)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    # observe_node drives the observer's futures internally via
    # spin_until_future_complete, so the observer must NOT be on the spinning
    # executor.
    failures = []

    # --- Check 1: type hash populated -------------------------------------- #
    import time
    deadline = time.monotonic() + 10.0
    infos = []
    while time.monotonic() < deadline:
        infos = observer.get_publishers_info_by_topic('/demo/chatter')
        infos = [i for i in infos if i.node_name == 'smoke_target']
        if infos:
            break
        time.sleep(0.2)
    if not infos:
        failures.append('CHECK1: never discovered /demo/chatter publisher')
    else:
        h = infos[0].topic_type_hash
        nonzero = any(b != 0 for b in bytes(h.value))
        print(f'CHECK1 type_hash: version={h.version} '
              f'value[:8]={list(bytes(h.value)[:8])} nonzero={nonzero}')
        if not nonzero:
            failures.append('CHECK1: topic_type_hash is all zeros (not populated)')

    # --- Check 2: observe_node end-to-end ---------------------------------- #
    try:
        msg = observe_node(observer, '/demo/smoke_target', timeout_sec=8.0)
    except Exception as e:  # noqa: BLE001
        failures.append(f'CHECK2: observe_node raised {e!r}')
        msg = None

    if msg is not None:
        print('CHECK2 observed Node:')
        print(to_yaml(msg))
        pub_names = [p.name for p in msg.publishers]
        sub_names = [s.name for s in msg.subscriptions]
        srv_names = [s.name for s in msg.service_servers]
        act_names = [a.name for a in msg.action_servers]
        param_names = [p.name for p in msg.parameters]
        if '/demo/chatter' not in pub_names:
            failures.append(f'CHECK2: /demo/chatter missing from publishers {pub_names}')
        if '/demo/commands' not in sub_names:
            failures.append(f'CHECK2: /demo/commands missing from subscriptions {sub_names}')
        if '/demo/add' not in srv_names:
            failures.append(f'CHECK2: /demo/add missing from service_servers {srv_names}')
        if '/demo/fibonacci' not in act_names:
            failures.append(f'CHECK2: /demo/fibonacci missing from action_servers {act_names}')
        # Action constituents must be folded, not left flat.
        if any('/_action/' in n for n in srv_names + sub_names + pub_names):
            failures.append('CHECK2: an _action/* constituent leaked into a flat list')
        if 'speed' not in param_names:
            failures.append(f'CHECK2: parameter "speed" missing from {param_names}')
        # Topic in the observed message must carry the real type hash.
        chatter = next((p for p in msg.publishers if p.name == '/demo/chatter'), None)
        if chatter is not None and not any(b != 0 for b in bytes(chatter.type.hash.value)):
            failures.append('CHECK2: observed /demo/chatter has all-zero type hash')

    executor.shutdown()
    spin_thread.join(timeout=2.0)
    observer.destroy_node()
    target.destroy_node()
    rclpy.shutdown()

    if failures:
        print('SMOKE FAILED:')
        for f in failures:
            print('  -', f)
        raise SystemExit(1)
    print('SMOKE OK')


if __name__ == '__main__':
    main()
