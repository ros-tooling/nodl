# nodl_observe

Observe a **running** node and produce its runtime description as a
`rosgraph_msgs/Node` message — stage one of the Observe → Describe pipeline:

```
running node --[ Observe ]--> rosgraph_msgs/Node --[ Describe ]--> NoDL document
```

Observe *records*: everything observable about the node — every endpoint
(including infrastructure like `/rosout`, `/parameter_events`, and the
parameter services), actual QoS, type hashes, parameter descriptors and
current values — unfiltered. Deciding what counts as "the node's interface"
is *interpretation*, which belongs to Describe.

## API

```python
import rclpy
from nodl_observe import observe_node

rclpy.init()
node = rclpy.create_node('observer')
msg = observe_node(node, '/my_namespace/my_node', timeout_sec=5.0)
```

`observe_node` never creates or spins its own node; it uses the caller's node
for graph queries and (unless `include_parameters=False`) the target's
parameter services. `timeout_sec` is a ceiling shared across discovery
polling and all parameter round-trips — it returns as soon as the graph
settles. Serializers live in `nodl_observe.serialization` (`to_yaml`,
`to_json`); the QoS profile of the latched CLI publish is exposed as
`nodl_observe.latched_qos()`.

The CLI front-end is `ros2 nodl describe` (in the `ros2nodl` package).

## Observability limits

Not every `Node.msg` field is observable from an external process:

| Entity | What is filled |
|---|---|
| publishers / subscriptions | name, type, QoS, and RIHS type hash via the info-by-topic graph queries |
| service servers / clients | name and types only; **QoS is reported as `*_UNKNOWN`** — there is no info-by-service API in rclpy/rmw — and the type hash is unset |
| action servers / clients | derived: the hidden `<action>/_action/*` entities are folded into each `Action` entry (topics get real QoS, services get UNKNOWN). Orphan `_action/*` entities stay flat — nothing is discarded |

Per-RMW gaps surface honestly rather than being papered over. Under the
pinned test RMW (`rmw_fastrtps_cpp`), the history policy of a remote endpoint
is **not** propagated over DDS discovery: a `KEEP_ALL` publisher is observed
(and golden-recorded) as `HISTORY_UNKNOWN`, while reliability, durability,
depth, and deadline come through. These limits are locked in by tests — if a
future rclpy exposes service QoS or history propagation, a test fails and
flags the upgrade opportunity.

Requires `rosgraph_msgs >= 2.0.4` (the release that introduces `Node.msg`).

## Tests and golden files

`test/expected/<ROS_DISTRO>/` holds golden YAML/JSON renders of three
scenario graphs (minimal, full-surface, multi-node isolation). Goldens are
per-distro because implicit endpoint sets and QoS observability shift between
releases; a distro without goldens skips with a bootstrap hint. Regenerate
with `REGEN_GOLDENS=1` and inspect the diff before committing.

The golden YAMLs are real `rosgraph_msgs/Node` samples and double as input
fixtures for Describe — a NoDL converter can be developed against them
without running a single node.
