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

**Per-RMW gaps surface honestly rather than being papered over.** The *full*
observation — every QoS policy a remote endpoint exposes over discovery — is
the baseline; some `(distro, RMW)` combinations observe strictly *less*, and
those gaps are recorded faithfully (never fabricated). Reliability, durability,
and deadline come through everywhere; the two known gaps are:

- **`rmw_fastrtps_cpp` on jazzy** does not propagate history or depth over
  discovery (`history → UNKNOWN`, `depth → 0`). Newer fastrtps (kilted onward)
  does — so this is version-specific, not inherent to fastrtps.
- **`rmw_cyclonedds_cpp`** reports a `KEEP_ALL` queue's `depth` as `0` (it does
  observe the `KEEP_ALL` history policy). `rmw_zenoh_cpp` reports the actual
  depth.

These are locked in by tests across the RMW matrix — if a future rclpy/RMW
exposes service QoS or changes history/depth propagation, the affected golden
*and* the targeted assertion both move, flagging it.

Requires **Iron or newer** and a `rosgraph_msgs` that provides `Node.msg`. The
graph messages are now released across jazzy (`2.0.4`), kilted (`2.3.2`),
lyrical (`2.4.5`), rolling (`2.5.0`), and even humble (`1.2.3`) — all via
ros2-testing where they lead the main index. **Humble works as a message but
not as a runtime target**: it predates Iron, so it lacks REP-2011 topic type
hashes and the `BEST_AVAILABLE` QoS enum, and its `builtin_interfaces/Duration`
overflows on an infinite QoS deadline. The observation tests are therefore
capability-gated to Iron+ (so humble's CI leg skips cleanly); full pre-Iron
support is a tracked follow-up.

## Tests and golden files

Golden YAML renders of three scenario graphs (minimal, full-surface,
multi-node isolation) are **deduplicated** across `(distro, RMW)`: most
combinations observe the same thing, so the common result is stored once and
only genuine differences get their own file. The test resolves most-specific
first:

```
test/expected/
  _base/<scenario>.yaml            # the full/canonical observation (most combos)
  <rmw>/<scenario>.yaml            # an RMW-inherent difference, on every distro
  <distro>/<rmw>/<scenario>.yaml   # a distro+RMW-specific difference
```

For example, four distros × three RMWs collapse to: `_base/` (the full
observation), `rmw_cyclonedds_cpp/s2_node.yaml` (cyclonedds's `KEEP_ALL`
depth-0 quirk, all distros), and `jazzy/rmw_fastrtps_cpp/` (jazzy's older
fastrtps, which alone drops history/depth). A `(distro, RMW)` with no golden
anywhere skips with a bootstrap hint.

Only one representation (YAML) is committed — the canonical, human-readable
form. The JSON renderer is proven by an equivalence test (both renders of the
same message must parse to the same structure), so no duplicate JSON golden is
stored.

**Adding an RMW or distro to CI** is designed to be "drop in goldens":

1. add it to the `rmw:` (or `ros:`/`ubuntu:`) matrix in
   `.github/workflows/test.yml` — the install step derives the apt package
   name from the RMW (`rmw_x_cpp` → `ros-<distro>-rmw-x-cpp`);
2. run the integration tests under that `(distro, RMW)` with `REGEN_GOLDENS=1`
   (writes the most-specific `<distro>/<rmw>/` location), then **promote**: if
   the new goldens match an existing `_base/` or `<rmw>/` set, delete the
   redundant copies; otherwise keep them as the override.

The golden for each `(distro, RMW)` is the lock on its exact observed values
(including the per-combination history/depth differences). The harness needs no
per-RMW setup — every scenario runs in one process / one session, so even a
router-based middleware like `rmw_zenoh_cpp` discovers without a separate
daemon.

The golden YAMLs are real `rosgraph_msgs/Node` samples and double as input
fixtures for Describe — a NoDL converter can be developed against them
without running a single node.
