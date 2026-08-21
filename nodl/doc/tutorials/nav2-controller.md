# Nav2: compose a C++ server and Python client

This tutorial uses one real Nav2 example in two ways. The C++ `ControllerServer` demonstrates interfaces inherited
from a framework base. Python `BasicNavigator` demonstrates a reusable bundle of clients used by a navigation
application.

```text
example_nav_to_pose (Python)
└── BasicNavigator
    ├── action clients and service clients ──> Nav2 servers
    └── localization topics

Nav2 bringup
└── ControllerServer (C++)
    ├── nav2::LifecycleNode ──> lifecycle services
    └── controller interface ────> FollowPath and controller topics
```

The reviewed sources are pinned to Navigation2 commit `b356ac1`:

- [`tb3_simulation_launch.py`](https://github.com/ros-navigation/navigation2/blob/b356ac1f8512bcc5f9b595562139f5b02095319b/nav2_bringup/launch/tb3_simulation_launch.py)
- [`controller_server.cpp`](https://github.com/ros-navigation/navigation2/blob/b356ac1f8512bcc5f9b595562139f5b02095319b/nav2_controller/src/controller_server.cpp)
- [`robot_navigator.py`](https://github.com/ros-navigation/navigation2/blob/b356ac1f8512bcc5f9b595562139f5b02095319b/nav2_simple_commander/nav2_simple_commander/robot_navigator.py)
- [`example_nav_to_pose.py`](https://github.com/ros-navigation/navigation2/blob/b356ac1f8512bcc5f9b595562139f5b02095319b/nav2_simple_commander/nav2_simple_commander/example_nav_to_pose.py)

> **Launch → Describe → Compose → Generate → Conform → Attribute**

:::{warning}
**Capability status:** The upstream launch and examples are real. NoDL `main` can describe running nodes, validate
direct endpoints, and resolve schema-level `include`. Generated bindings, scoped conformance, and ownership-aware
reporting below are a draft workflow; they are not implemented on `main`.
:::

## 1. Launch the official Nav2 example

Start the all-in-one TurtleBot 3 simulation provided by `nav2_bringup`:

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False
```

This launches the simulator, robot state publisher, Nav2 bringup, lifecycle managers, and RViz. Wait for Nav2 to
activate, then verify that `/controller_server` is present:

```bash
ros2 node list
ros2 lifecycle get /controller_server
```

The simulation is the shared fixture for both parts below. The tutorial does not invent a replacement Nav2 launch
file or parameter set.

## Part A: C++ provider composition

`ControllerServer` is the provider-side example. It owns its controller action and topics, while its
`nav2::LifecycleNode` base owns the standard lifecycle interface.

### 2. Describe the configured ControllerServer

Recover the interface of the node that is actually running in the official example:

```bash
ros2 nodl describe /controller_server \
  -o /tmp/controller_server.observed.nodl.yaml
```

The observed document reflects the selected plugins, parameter file, namespace, and ROS distribution. Curate it into
a teaching contract instead of assuming that source-level defaults describe every deployment.

### 3. Compose the lifecycle base

The reusable capability declares the endpoints supplied by `nav2::LifecycleNode`:

```yaml
# nav2_ros_common/nodl/lifecycle_node.nodl.yaml
nodl_version: 2
codegen:
  cpp:
    role: base_class
    header: nav2_ros_common/lifecycle_node.hpp
    class: nav2::LifecycleNode
service_servers:
  - {name: ~/change_state, type: lifecycle_msgs/srv/ChangeState}
  - {name: ~/get_state, type: lifecycle_msgs/srv/GetState}
  - {name: ~/get_available_states, type: lifecycle_msgs/srv/GetAvailableStates}
  - {name: ~/get_available_transitions, type: lifecycle_msgs/srv/GetAvailableTransitions}
  - {name: ~/get_transition_graph, type: lifecycle_msgs/srv/GetAvailableTransitions}
publishers:
  - name: ~/transition_event
    type: lifecycle_msgs/msg/TransitionEvent
    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}
```

The root document includes the capability and declares a deliberately scoped controller surface:

```yaml
# nodl/controller_server.nodl.yaml
nodl_version: 2
include:
  - ref: nodl://nav2_ros_common/lifecycle_node
publishers:
  - name: transformed_global_plan
    type: nav_msgs/msg/Path
    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}
  - name: tracking_feedback
    type: nav2_msgs/msg/TrackingFeedback
    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}
subscriptions:
  - name: speed_limit
    type: nav2_msgs/msg/SpeedLimit
    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}
action_servers:
  - name: follow_path
    type: nav2_msgs/action/FollowPath
```

Validate the resolved contract after curation:

```bash
ros2 nodl validate nodl/controller_server.nodl.yaml
```

Preserving the include boundary lets a later diff distinguish an inherited lifecycle failure from a
controller-owned failure.

### 4. Generate and conform the provider

:::{warning}
**Draft workflow — not yet implemented.** Generation must interpret the included C++ base metadata. Conformance must
preserve include provenance and support comparing only the declared teaching scope.
:::

Generate the interface binding while retaining ControllerServer's plugins, costmap behavior, TF lookups, and control
loop:

```bash
ros2 nodl generate nodl/controller_server.nodl.yaml \
  --language cpp --output generated/controller_server
colcon build --packages-select nav2_controller
```

Launch the same TurtleBot example with the NoDL-forward ControllerServer, then compare its declared surface:

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py \
  headless:=False controller_interface:=nodl
ros2 nodl conform /controller_server \
  --file nodl/controller_server.nodl.yaml --scope declared
```

`--scope declared` compares every declared endpoint without treating parameter-dependent or infrastructure endpoints
outside this teaching contract as failures. A strict comparison requires a complete contract curated from this
fixture's observed document.

### 5. Attribute a provider failure

A small test probe is still useful, but it is now only the failure lab. Its normal variant exposes the selected
controller endpoints through the generated lifecycle base. Its `base:=plain` variant keeps the controller endpoints
but derives from `rclcpp::Node`, omitting the inherited lifecycle capability.

```bash
ros2 launch nodl_nav2_controller_test controller_contract_probe.launch.py base:=plain
ros2 nodl conform /controller_server \
  --file nodl/controller_server.nodl.yaml --scope declared
```

Expected ownership-aware result:

```text
FAIL: /controller_server/change_state is missing
  declared by: nodl://nav2_ros_common/lifecycle_node
  capability: nav2::LifecycleNode
```

The probe isolates an otherwise difficult regression. It does not replace the real Nav2 system used in steps 1–4.

## Part B: Python client capabilities

:::{admonition} Optional section under review
This section tests whether the Nav2 tutorial benefits from showing both sides of the same running system. It can be
removed later without changing the ControllerServer tutorial above.
:::

`BasicNavigator` is not another server. It is a Python `rclpy.node.Node` that bundles action clients, service clients,
an initial-pose publisher, and an AMCL-pose subscription into a reusable navigation API.

### 6. Run and describe the upstream Python example

With the TurtleBot simulation still running, start Nav2's installed example:

```bash
ros2 run nav2_simple_commander example_nav_to_pose
```

While the robot is navigating, recover the client-side graph interface:

```bash
ros2 nodl describe /basic_navigator \
  -o /tmp/basic_navigator.observed.nodl.yaml
```

This is a different view of the same system. `/controller_server` provides actions and topics; `/basic_navigator`
consumes capabilities from several Nav2 servers. Presence of an action client does not prove that a goal succeeds.

### 7. Compose reusable client capabilities

Instead of repeating every client in each Python navigation application, group them by purpose:

```yaml
# nav2_simple_commander/nodl/navigation_actions.nodl.yaml
nodl_version: 2
action_clients:
  - {name: navigate_to_pose, type: nav2_msgs/action/NavigateToPose}
  - {name: follow_path, type: nav2_msgs/action/FollowPath}
  - {name: compute_path_to_pose, type: nav2_msgs/action/ComputePathToPose}
```

```yaml
# nav2_simple_commander/nodl/localization_client.nodl.yaml
nodl_version: 2
publishers:
  - name: initialpose
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE, durability: VOLATILE}
subscriptions:
  - name: amcl_pose
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    qos: {history: KEEP_LAST, depth: 1, reliability: RELIABLE, durability: TRANSIENT_LOCAL}
```

The `BasicNavigator` document composes those capabilities and adds selected service clients:

```yaml
# nodl/basic_navigator.nodl.yaml
nodl_version: 2
include:
  - ref: nodl://nav2_simple_commander/navigation_actions
  - ref: nodl://nav2_simple_commander/localization_client
service_clients:
  - name: map_server/load_map
    type: nav2_msgs/srv/LoadMap
  - name: global_costmap/clear_entirely_global_costmap
    type: nav2_msgs/srv/ClearEntireCostmap
  - name: local_costmap/clear_entirely_local_costmap
    type: nav2_msgs/srv/ClearEntireCostmap
```

This is deliberately a teaching scope. The production `BasicNavigator` also creates clients for waypoint following,
route tracking, smoothing, docking, recoveries, costmap queries, collision monitoring, and lifecycle management.

:::{note} Includes describe a static interface profile, not an available Nav2 mode
Nav2 deployments enable different capability subsets. A localization deployment, a SLAM deployment, and a system
with docking or route tracking do not necessarily run the same servers.

Including `navigation_actions` above means that those client endpoints belong to the resolved
`BasicNavigator` contract and generated binding. It does **not** mean that matching action servers are running, or
that a navigation goal will succeed. These are three separate claims:

1. the client endpoint is created;
2. a compatible server is available in this deployment; and
3. the requested behavior succeeds.

NoDL version 2 includes are static; they do not select fragments from runtime Nav2 configuration. Model deployment
variants as explicit root documents instead. For example, a core profile can include `navigation_actions` and
`localization_client`, while a fuller profile can additionally include fragments such as `route_client`,
`docking_client`, or `gps_waypoint_client`. Conformance checks the selected graph contract. Nav2 launch and behavior
tests check server availability and successful operation.
:::

### 8. Generate and conform the Python client

:::{warning}
**Draft workflow — not yet implemented.** Python generation must compose client capabilities and leave goal creation,
feedback handling, cancellation, and task-result policy in `BasicNavigator`.
:::

```bash
ros2 nodl generate nodl/basic_navigator.nodl.yaml \
  --language python --output generated/basic_navigator
colcon build --packages-select nodl_nav2_client_demo
ros2 run nodl_nav2_client_demo example_nav_to_pose
ros2 nodl conform /basic_navigator \
  --file nodl/basic_navigator.nodl.yaml --scope declared
```

Generation owns the selected action, service, publisher, and subscription declarations. The existing Python methods
still construct goals, wait for servers, process feedback, cancel tasks, and interpret results.

For a client-side regression, omit the generated `follow_path` action client while leaving the contract unchanged.
Conformance should report the missing client and attribute it to
`nodl://nav2_simple_commander/navigation_actions`. The robot need not fail visibly until an application attempts to
use that capability.

## 9. Keep graph contracts and system behavior separate

Both parts use the same boundary:

| Requirement | NoDL graph contract? | Separate system check? |
|---|---|---|
| Expose the ControllerServer lifecycle services | Yes | No |
| Reach and remain in the active lifecycle state | No | Lifecycle integration test |
| Create a `follow_path` server or client | Yes | No |
| Accept and complete a navigation goal | No | Nav2 behavior test |
| Publish or subscribe to `/tf` and `/tf_static` | Yes | No |
| Provide `map → odom → base_link` | No | TF lookup or system test |
| Create a bond while active | Partly, when its endpoints are declared | Bond-state integration test |

The C++ section asks which framework layer owns a provider endpoint. The optional Python section asks whether a
reusable client capability can prevent every navigation application from restating the same interface.
