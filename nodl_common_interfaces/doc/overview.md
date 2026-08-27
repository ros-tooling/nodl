# nodl_common_interfaces

`nodl_common_interfaces` registers NoDL interface descriptions for the standard ROS 2 node base classes
with the ament index, so that `nodl://` include references resolve correctly.

This is a stopgap package.
Eventually, upstream packages (`rclcpp`, `rclcpp_lifecycle`) will ship their own `.nodl.yaml` files.
Until then, this package provides the descriptions and will be deprecated when upstream adopts them.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## Registered documents

| Reference | Describes |
|---|---|
| `nodl://rclcpp/node` | `rclcpp::Node` — publishers (`/rosout`, `/parameter_events`), parameter services, and `use_sim_time`. |
| `nodl://rclcpp_lifecycle/lifecycle_node` | `rclcpp_lifecycle::LifecycleNode` — includes `rclcpp::Node`, adds the `transition_event` publisher and lifecycle services (`change_state`, `get_state`, etc.). |

Both documents carry `codegen.cpp` metadata declaring them as `BASE_CLASS` providers, which is what `nodl_generator_cpp` uses to determine the generated class's base class.

## Usage

Any package that references a document registered by this package should list `nodl_common_interfaces` as a dependency:

```xml
<depend>nodl_common_interfaces</depend>
```

The NoDL documents are registered at install time via `ament_nodl_register`, so they must be built before any package whose NoDL references them.
