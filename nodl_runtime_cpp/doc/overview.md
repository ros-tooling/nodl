# nodl_runtime_cpp

`nodl_runtime_cpp` provides shared utilities for C++ nodes, especially those that `nodl_generator_cpp` generates.
It currently provides `rclcpp_lifecycle` wrapper classes to enable a reusable pattern for consistently managing the state and behavior of entities in Lifecycle nodes.

The package is header-only, and depends on `rclcpp` and `rclcpp_lifecycle`, which it exports.

```xml
<depend>nodl_runtime_cpp</depend>
```

```cmake
find_package(nodl_runtime_cpp REQUIRED)
target_link_libraries(my_node nodl_runtime_cpp::nodl_runtime_cpp)
```

## What it provides

### Lifecycle node

`nodl_runtime_cpp::LifecycleNode` derives `rclcpp_lifecycle::LifecycleNode` to provide a more opinionated and automated default behavior, and keeps its constructors.
It implements and marks as `final` the standard lifecycle methods (`on_configure`, `on_activate`, `on_deactivate`, `on_cleanup`, `on_shutdown` and `on_error`) to manage the node's endpoints in a standard way.
It provides new optional hooks for node authors to add behavior on each transition: `handle_configure`, `handle_activate`, `handle_deactivate`, `handle_cleanup`, `handle_shutdown` and `handle_error`.
Each hook takes the previous state and returns a `CallbackReturn`, and defaults to SUCCESS.
A subclass, generated or authored, defines the hook that matches the transition instead of an `on_*` method.

Lifecycle publishers follow the node state on every path with no author code, because the base class runs the standard activation and deactivation of `rclcpp_lifecycle::LifecycleNode` around the hooks.

| Transition | Order |
|---|---|
| configure | hook only, managed entities are not notified |
| activate | standard activation, then hook, and a result other than SUCCESS runs the standard deactivation and is returned |
| deactivate | hook, then standard deactivation if the hook returned SUCCESS |
| cleanup | hook only, managed entities are not notified |
| shutdown | standard deactivation, then hook |
| error | standard deactivation, then hook |

Only activation and deactivation reach managed entities, which includes the deactivation that runs on shutdown and error.
Configure and cleanup run only the hooks, so an entity registered with `add_managed_entity` does not receive them.

A hook that throws is turned into ERROR by `rclcpp_lifecycle`, which runs `on_error`.
When `handle_error` returns SUCCESS, the node ends unconfigured.

#### Example

This example shows a hand-written (non-generated) node using `nodl_runtime_cpp::LifecycleNode` to illustrate using the lifecycle hooks to add custom behavior on state transitions.
It publishes from `handle_activate` and logs from `handle_deactivate`.
Generated nodes derive the same class, so their authors implement the same hooks.

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: /// Example of a non-generated
:end-before: int main
```

The example is compiled as part of the package tests.

## Background

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.
Sealing the transition callbacks and offering hooks instead makes that standard behavior impossible to skip.
