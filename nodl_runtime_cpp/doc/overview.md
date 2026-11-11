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
An authored subclass defines the hook that matches the transition instead of an `on_*` method.

Lifecycle publishers follow the node state on every path with no author code, because the base class runs the standard activation and deactivation of `rclcpp_lifecycle::LifecycleNode` around the hooks.

#### Creating endpoints on activation

The base class keeps a registry of endpoints that exist only while the node is active.
Register them from the constructor of the authored class, with `manage` or `add_activation_slot`:

| Function | Registers |
|---|---|
| `manage(member, make)` | A `std::shared_ptr` member. `make` returns the endpoint at activation, and the member is reset at deactivation. |
| `add_activation_slot(create, destroy)` | A pair of functions, for anything that is not a single member. `destroy` must be safe to call when `create` has not run. |

Slots are created in registration order when the node activates, and destroyed in reverse order when it deactivates, shuts down or errors.
Register the endpoints that others use first, such as publishers before the subscriptions that publish.
A `create` that throws destroys the slots created before it, and the transition fails with an error.
Registering while the node is active throws `std::logic_error`.
A node that is destroyed while active destroys its members as usual, and the slots do not run.

A managed member is null while the node is not active.
Use it from the endpoint callbacks of the node, `handle_activate` and `handle_deactivate`, and create and cancel timers in those two hooks.
A thread of your own copies the `shared_ptr` and checks it for null.

| Transition | Order |
|---|---|
| configure | hook only |
| activate | create the slots, standard activation, then hook, and a result other than SUCCESS runs the standard deactivation, destroys the slots and is returned |
| deactivate | hook, then standard deactivation and slot destruction if the hook returned SUCCESS |
| cleanup | hook only |
| shutdown | destroy the slots, standard deactivation, then hook |
| error | destroy the slots, standard deactivation, then hook |

Destroying the slots does nothing when none is created, so a deactivation that already ran is not repeated by shutdown or error.
Configure and cleanup run only the hooks, so an entity registered with `add_managed_entity` does not receive them.
Only activation and deactivation reach managed entities, which includes the deactivation that runs on shutdown and error.

A hook that throws is turned into ERROR by `rclcpp_lifecycle`, which runs `on_error`.
When `handle_error` returns SUCCESS, the node ends unconfigured.

#### Example

This example shows a hand-written (non-generated) node using `nodl_runtime_cpp::LifecycleNode` to illustrate registering endpoints that exist only while the node is active, and using the lifecycle hooks to add custom behavior on state transitions.
It greets from `handle_activate` and from a timer that it creates there, and stops the timer in `handle_deactivate`.
Generated nodes derive the same class and register their endpoints with `manage`, so an authored class of a generated node defines the same hooks.

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: /// Example of a non-generated
:end-before: int main
```

The example is compiled as part of the package tests.

#### Trade-offs

- A latched publisher loses its history when it is destroyed at deactivation, so publish the latched message again in `handle_activate`.
- A message published in `handle_activate` reaches only the peers that are already matched, since discovery is asynchronous.
  A `transient_local` publisher delivers it to the peers that match later.
- Each activation creates the endpoints again, with the discovery traffic that comes with it.
- An inactive node shows none of its registered endpoints in the graph.

## Background

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.
Sealing the transition callbacks and offering hooks instead makes that standard behavior impossible to skip.

`rclcpp_lifecycle` has a lifecycle publisher and no lifecycle subscription, service, client or action type.
An entity created in the constructor is matched by the middleware and runs its callbacks in every state.
A `transient_local` subscription takes the publisher's history once, as soon as it matches, which is before the node is configured, and that sample is never delivered again.
Creating the endpoints at activation delivers it then, and matches the lifecycle design, in which an inactive node does not read topics.
