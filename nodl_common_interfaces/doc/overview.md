# nodl_common_interfaces

`nodl_common_interfaces` registers language-independent NoDL interface descriptions for the standard ROS 2 node base types.
Each description carries the C++ and Python code-generation metadata needed to select the corresponding client-library class.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## Registered documents

| Reference | Describes |
|---|---|
| `nodl://nodl_common_interfaces/node` | The standard node interface — publishers (`/rosout`, `/parameter_events`), parameter services, and `use_sim_time`. Selects `rclcpp::Node` or `rclpy.node.Node` for code generation. |
| `nodl://nodl_common_interfaces/lifecycle_node` | The standard lifecycle-node interface — includes `node`, adds the `transition_event` publisher and lifecycle services, and selects `rclcpp_lifecycle::LifecycleNode` or `rclpy.lifecycle.LifecycleNode`. |

Both documents carry `codegen.cpp` and `codegen.python` `BASE_CLASS` metadata.
Each generator reads only its own metadata while sharing the same interface contract and reference.

## Usage

The documents are resolved only while building and testing, never by a running node.
A package that references them without a generator in its build declares `nodl_common_interfaces` with `<build_depend>`, `<test_depend>`, or both, not `<depend>`.
This covers registering a hand-written document that includes them with `ament_nodl_register`, and conformance tests that load one:

```xml
<build_depend>nodl_common_interfaces</build_depend>
<test_depend>nodl_common_interfaces</test_depend>
```

`nodl_generator_cpp` and `nodl_generator_py` depend on `nodl_common_interfaces`, so a package that generates code does not have to explicitly declare it.

Tooling that resolves an installed document at runtime, such as `ros2 nodl` verbs on a registered document that includes these, needs `nodl_common_interfaces` installed, since a package that generates code does not depend on it at runtime.

The NoDL documents are registered at install time via `ament_nodl_register`, so they must be built before any package whose NoDL references them.
