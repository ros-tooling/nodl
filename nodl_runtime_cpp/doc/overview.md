# nodl_runtime_cpp

`nodl_runtime_cpp` is the C++ runtime for nodes written against `rclcpp_lifecycle`, including the nodes that `nodl_generator_cpp` generates.
It is header-only, and depends on `rclcpp` and `rclcpp_lifecycle`, which it exports.

```xml
<depend>nodl_runtime_cpp</depend>
```

```cmake
find_package(nodl_runtime_cpp REQUIRED)
target_link_libraries(my_node nodl_runtime_cpp::nodl_runtime_cpp)
```

## Lifecycle node

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.

`nodl_runtime_cpp::LifecycleNode` derives `rclcpp_lifecycle::LifecycleNode` and keeps its constructors.
It marks `on_configure`, `on_activate`, `on_deactivate`, `on_cleanup`, `on_shutdown` and `on_error` `final`, and calls optional hooks instead.
Each hook takes the previous state and returns a `CallbackReturn`, and defaults to SUCCESS:
`handle_configure`, `handle_activate`, `handle_deactivate`, `handle_cleanup`, `handle_shutdown` and `handle_error`.

| Transition | Order |
|---|---|
| configure | hook |
| activate | standard activation, then hook, and a result other than SUCCESS runs the standard deactivation and is returned |
| deactivate | hook, then standard deactivation if the hook returned SUCCESS |
| cleanup | hook |
| shutdown | standard deactivation, then hook |
| error | standard deactivation, then hook |

The standard activation and deactivation are those of `rclcpp_lifecycle::LifecycleNode`, so every lifecycle publisher follows the node state on every path, with no author code.
A hook that throws is turned into ERROR by `rclcpp_lifecycle`, which runs `on_error`.

### Example

A hand-written node that publishes from `handle_activate` and logs from `handle_deactivate`:

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: /// Publishes a greeting
:end-before: int main
```

The example is compiled as part of the package tests.
