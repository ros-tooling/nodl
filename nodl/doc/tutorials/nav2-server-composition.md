# Nav2: compose a server contract

The previous tutorial migrated a client while every Nav2 server remained conventional.
This tutorial moves to the other side of that boundary and composes a contract for the Nav2 Controller Server.

The Controller Server does not own every interface it exposes.
Its `nav2::LifecycleNode` base supplies lifecycle services and events; the server supplies navigation interfaces such as
`FollowPath`.

```text
controller_server
├── include: rclcpp_lifecycle::LifecycleNode
│   └── lifecycle services and transition events
└── Controller Server interfaces
    ├── follow_path
    └── speed_limit
```

Composition keeps each interface with its implementation instead of copying lifecycle endpoints into every Nav2
server contract.

## 1. Identify interface ownership

Launch the same TurtleBot 3 Nav2 system used in the previous tutorial:

```bash
export TURTLEBOT3_MODEL=waffle
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False
```

Inspect both parts of the Controller Server boundary:

```bash
ros2 lifecycle get /controller_server
ros2 action info /follow_path
ros2 topic info /speed_limit --verbose
```

The lifecycle interface is shared by Nav2 lifecycle nodes.
The action and subscription belong to the Controller Server.
A composed contract should preserve that ownership boundary.

## 2. Compose the Controller Server contract

Include the standard lifecycle contract, then declare only the interfaces the Controller Server owns:

```{literalinclude} ../../../examples/nodl_tutorials/controller_server_nodl/nodl/controller_server.nodl.yaml
:language: yaml
```

The `nodl://` reference resolves the registered `rclcpp_lifecycle::LifecycleNode` contract through the ament index.
That reusable contract contributes lifecycle services, transition events, parameters, and ordinary node interfaces.

The checked-in contract selects two interfaces to keep the ownership example readable.
A production deployment contract should add every Controller Server endpoint for its supported Nav2 configuration.

## 3. Register and verify the composition

Register the composed document in the package build:

```{literalinclude} ../../../examples/nodl_tutorials/controller_server_nodl/CMakeLists.txt
:language: cmake
:lines: 6-9
:emphasize-lines: 4
```

Build the package, then validate the installed include chain:

```bash
colcon build --packages-up-to controller_server_nodl
source install/setup.bash
ros2 nodl validate \
  install/controller_server_nodl/share/controller_server_nodl/nodl/controller_server.nodl.yaml
```

```text
install/controller_server_nodl/share/controller_server_nodl/nodl/controller_server.nodl.yaml: ok
```

Run the fixture tests:

```bash
colcon test --packages-select controller_server_nodl
colcon test-result --verbose
```

The tests verify registration and resolve the include to produce one contract containing both `follow_path` and
lifecycle endpoints such as `~/change_state`.

## 4. Apply the pattern upstream

The full Controller Server contract can be used for runtime conformance once it contains every observable endpoint in
a supported configuration.
Code generation is a separate integration step.
Before generating the server, `nav2_ros_common` should own a NoDL implementation boundary for
`nav2::LifecycleNode`; the generated base must then fit Nav2's existing constructor, lifecycle callbacks, plugins, and
control loop without taking ownership of that behavior.

The important result is the ownership model:

- the ROS lifecycle package owns the reusable lifecycle interface contract;
- `nav2_controller` owns Controller Server endpoints and includes that interface; and
- consumers resolve one complete interface without either package duplicating the other's definitions.
