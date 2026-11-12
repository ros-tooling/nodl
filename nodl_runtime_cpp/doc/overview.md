# nodl_runtime_cpp

`nodl_runtime_cpp` is a header-only package providing shared utilities for C++ nodes, especially those that `nodl_generator_cpp` generates.

It currently provides a wrapper class for `rclcpp_lifecycle::LifecycleNode` to enable a reusable pattern for consistently managing the state and behavior of endpoint entities.
Subscriptions are created when the node activates and destroyed when it deactivates.

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

### Endpoints created on activation

The node keeps a registry of activation slots, each a pair of functions that create and destroy one endpoint.
Register slots from the constructor, in the order the endpoints must be created.
The node creates the registered endpoints when it activates and destroys them when it deactivates, so the endpoint does not exist in any other state.

`manage(member, make)` registers a `std::shared_ptr` member and a function that returns the endpoint to assign to it.
The member is null while the node is not active, and the type of the endpoint is the type of the member.
`add_activation_slot(create, destroy)` is the general form, for an endpoint that is not held in a single `std::shared_ptr` member.

A generated node derived from this class registers its subscriptions with `manage` in its constructor.
An authored node registers its own endpoints the same way:

```cpp
manage(sub_name_, [this] {
  return create_subscription<std_msgs::msg::String>("name", rclcpp::QoS(10), std::bind(&Greeter::on_name, this, std::placeholders::_1));
});
```

Slots follow these rules:

- Slots are created in registration order and destroyed in reverse order.
- `destroy` runs on deactivation, shutdown and error from the active state, and when `handle_activate` fails or a later slot throws.
- A `create` that throws destroys the slots created before it, and the activation ends in ERROR.
- Registering a slot while the node is activating or active throws `std::logic_error`, including from a `create`.
- The node's destructor never calls `destroy`.
- Destroying the slots wakes the executor that spins the node, so the executor releases the endpoints it still holds.

A subscription member is null while the node is inactive, so use it only where the node is active:
callbacks in the default callback group, timers that `handle_activate` creates, and the hooks.
Other threads must not read the member, since the transition resets it.

Creating endpoints on activation has these costs:

- A message published while the node is inactive is not received by a volatile subscription.
- Discovery of the new subscription starts at activation, so a publisher may take a moment to match it.
- Activation fails if an endpoint cannot be created.

### State transitions

| Transition | Order |
|---|---|
| configure | hook only |
| activate | standard activation, create the slots, then hook. A result other than SUCCESS destroys the slots and runs the standard deactivation, and an exception destroys the slots |
| deactivate | hook, then if the hook returned SUCCESS destroy the slots and run the standard deactivation |
| cleanup | hook only |
| shutdown from active | `handle_deactivate`, destroy the slots, standard deactivation, then `handle_shutdown` |
| error from active | `handle_deactivate`, destroy the slots, standard deactivation, then `handle_error` |
| shutdown or error from unconfigured or inactive | hook only |

Some behavior specifics:

- On shutdown and error from the active state `handle_deactivate` runs first, so custom logic such as stopping timers and threads runs on every path that leaves the active state.
- A shutdown cannot be vetoed, so a result other than SUCCESS (including exceptions) from `handle_deactivate` on these paths is logged and ignored, and the shutdown or error hook runs regardless.
- An error that `handle_deactivate` caused by throwing does not run it again.
- A failed or throwing `handle_activate` does not run `handle_deactivate`.
- `handle_activate` can rely on the slots having been created, and a failing hook leaves the node inactive with the slots destroyed.
- A failing `handle_deactivate` leaves the node active and keeps the slots.
- Create timers and start threads last in `handle_activate`, so that a failing hook leaves none of them firing on null members.
- A hook that throws is turned into ERROR by `rclcpp_lifecycle`, which runs `on_error`.
- When `handle_error` returns SUCCESS, the node ends unconfigured.

### Example

This example shows a hand-written (non-generated) node using `nodl_runtime_cpp::LifecycleNode` to illustrate using the lifecycle hooks to add custom behavior on state transitions.
It registers a subscription with `manage`, greets from `handle_activate` and from a timer that it creates there, and stops the timer in `handle_deactivate`.
Generated nodes derive the same class and register their subscriptions with `manage`, so an authored implementation of a generated node defines the same hooks.

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: /// Example of a non-generated
:end-before: int main
```

### Background

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.
Sealing the transition callbacks and offering hooks instead makes that standard behavior impossible to skip.

A subscription that exists while the node is inactive receives messages, and a `transient_local` subscription also receives the latched messages published before the node was configured.
Those messages run the callbacks of a node that is not active, even though a lifecycle node is expected to do no work until it activates.
Creating the subscription on activation delivers them after the node is active, and leaves them unconsumed until then.
It also removes the subscription from the graph while the node is inactive.
