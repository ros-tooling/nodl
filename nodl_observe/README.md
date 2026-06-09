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

**Per-RMW gaps surface honestly rather than being papered over**, and which
QoS policies a remote endpoint exposes over DDS discovery genuinely differs by
middleware. Reliability, durability, and deadline come through everywhere;
history and depth do not:

| QoS field on a remote topic | `rmw_fastrtps_cpp` | `rmw_cyclonedds_cpp` |
|---|---|---|
| reliability / durability / deadline | observed | observed |
| history policy | `*_UNKNOWN` (not propagated) | observed (e.g. `KEEP_ALL`) |
| depth | `0` (not propagated) | observed (actual depth) |

These limits are locked in by tests against **both** RMWs — observation never
fabricates a requested-but-unobserved value, and the golden for each
`(distro, RMW)` records exactly what that combination reports. If a future
rclpy/RMW exposes service QoS or changes history/depth propagation, the
golden diff *and* the targeted assertion both move, flagging it.

Requires `rosgraph_msgs >= 2.0.4` (the release that introduces `Node.msg`).

## Tests and golden files

`test/expected/<ROS_DISTRO>/<RMW>/` holds golden YAML renders of three scenario
graphs (minimal, full-surface, multi-node isolation). Goldens are keyed by
`(distro, RMW)` because implicit endpoint sets and QoS observability shift
between releases *and* middlewares; when every RMW on a distro observes the
same thing, the set is committed once at the `<distro>/` level instead (the
test resolves most-specific first). A `(distro, RMW)` with no golden skips with
a bootstrap hint. Regenerate with `REGEN_GOLDENS=1` and inspect the diff before
committing.

Only one representation (YAML) is committed per `(distro, RMW)` — it is the
canonical, human-readable form. The JSON renderer is proven by an equivalence
test (both renders of the same message must parse to the same structure), so
no duplicate JSON golden is stored.

The golden YAMLs are real `rosgraph_msgs/Node` samples and double as input
fixtures for Describe — a NoDL converter can be developed against them
without running a single node.
