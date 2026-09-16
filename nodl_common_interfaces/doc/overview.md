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

Any package that references a document registered by this package should list `nodl_common_interfaces` as a dependency:

```xml
<depend>nodl_common_interfaces</depend>
```

The NoDL documents are registered at install time via `ament_nodl_register`, so they must be built before any package whose NoDL references them.
