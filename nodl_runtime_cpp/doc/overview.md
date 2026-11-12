# nodl_runtime_cpp

`nodl_runtime_cpp` is a header-only package providing shared utilities for C++ nodes, especially those that `nodl_generator_cpp` generates.

It currently provides a wrapper class for `rclcpp_lifecycle::LifecycleNode` to enable a reusable pattern for consistently managing the state and behavior of endpoint entities.

```xml
<depend>nodl_runtime_cpp</depend>
```

```cmake
find_package(nodl_runtime_cpp REQUIRED)
target_link_libraries(my_node nodl_runtime_cpp::nodl_runtime_cpp)
```

## Lifecycle node

`nodl_runtime_cpp::LifecycleNode` derives `rclcpp_lifecycle::LifecycleNode` to provide a more opinionated and automated default behavior.
It implements and marks as `final` the standard lifecycle methods (`on_configure`, `on_activate`, `on_deactivate`, `on_cleanup`, `on_shutdown` and `on_error`) to manage the node's endpoints in a standard way.
It provides new optional hooks for node authors to add custom behavior on each transition: `handle_configure`, `handle_activate`, `handle_deactivate`, `handle_cleanup`, `handle_shutdown` and `handle_error`.
Each hook takes the previous state and returns a `CallbackReturn` -- the default implementations just return `SUCCESS`.
An authored subclass defines the hook that matches the transition instead of an `on_*` method.

### State transitions

| Transition | Order |
|---|---|
| configure | hook only |
| activate | standard activation, then hook. A result other than SUCCESS, or an exception, runs the standard deactivation and destroys the slots |
| deactivate | hook, then standard deactivation if the hook returned SUCCESS |
| cleanup | hook only |
| shutdown from active | `handle_deactivate`, standard deactivation, then `handle_shutdown` |
| error from active | `handle_deactivate`, standard deactivation, then `handle_error` |
| shutdown or error from unconfigured or inactive | hook only |

Some behavior specifics:

- On shutdown and error from the active state `handle_deactivate` runs first, so custom logic such as stopping timers and threads runs on every path that leaves the active state.
- A shutdown cannot be vetoed, so a result other than SUCCESS (including exceptions) from `handle_deactivate` on these paths is logged and ignored, and the shutdown or error hook runs regardless.
- An error that `handle_deactivate` caused by throwing does not run it again.
- A failed or throwing `handle_activate` does not run `handle_deactivate`.
- Create timers and start threads last in `handle_activate`, so that a failing hook leaves none of them firing on null members.
- A hook that throws is turned into ERROR by `rclcpp_lifecycle`, which runs `on_error`.
- When `handle_error` returns SUCCESS, the node ends unconfigured.

### Example

This example shows a hand-written (non-generated) node using `nodl_runtime_cpp::LifecycleNode` to illustrate using the lifecycle hooks to add custom behavior on state transitions.
It greets from `handle_activate` and from a timer that it creates there, and stops the timer in `handle_deactivate`.
Generated nodes derive the same class and register their endpoints with `manage`, so an authored implementation of a generated node defines the same hooks.

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: /// Example of a non-generated
:end-before: int main
```

### Background

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.
Sealing the transition callbacks and offering hooks instead makes that standard behavior impossible to skip.
