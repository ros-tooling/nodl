# nodl_runtime_cpp

`nodl_runtime_cpp` provides shared utilities for C++ nodes, especially those that `nodl_generator_cpp` generates.
It currently provides `rclcpp_lifecycle` wrapper classes to enable a reusable pattern for consistently managing the state and behavior of entities in Lifecycle nodes.

The package is header-only, and depends on `rclcpp`, `rclcpp_action` and `rclcpp_lifecycle`, which it exports.

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
Generated nodes derive the same class, so an authored subclass of a generated node defines the same hooks.

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: /// Example of a non-generated
:end-before: using AddTwoInts
```

The example is compiled as part of the package tests.

### Active-only entities

A lifecycle node has the ability to block subscription messages, service requests and client requests while it is inactive.
`active_only_subscription_callback`, `create_active_only_service`, `GatedClient` and `GatedActionClient` each put one entity behind the node's activation gate.
The entity is still created in the constructor, as usual.

`nodl_runtime_cpp::LifecycleNode` owns the gate, a `nodl_runtime_cpp::Gate`, which is an alias of `rclcpp_lifecycle::SimpleManagedEntity`.
The standard activation opens it, before `handle_activate` runs, and the standard deactivation closes it, together with every lifecycle publisher.
Subclasses read it through the protected `gate()`, which returns a read-only `GatePtr`.
The helpers take the gate, not the node, so they also work with a gate that a non-generated `rclcpp_lifecycle::LifecycleNode` registers with `add_managed_entity` itself.

| Entity | Helper | While the gate is closed |
|---|---|---|
| Subscription | `active_only_subscription_callback` | The message is dropped and the callback is not called. |
| Service server | `create_active_only_service` | The request is dropped and no response is sent, so the client's request never completes. |
| Service client | `GatedClient` | `async_send_request` throws `InactiveError`. |
| Action client | `GatedActionClient` | `async_send_goal` throws `InactiveError`. |

Clients throw instead of dropping, because a dropped request would return a future that never completes.
The gate is already open in `handle_activate`, so that hook can call a client, but `handle_configure` cannot.
Move requests made at configure time, such as fetching configuration from another node, to `handle_activate`.
These are not gated:

- waiting for a service or an action server, and checking whether it is ready, so `wait_for_service` works in `handle_configure`
- responses to requests sent while the gate was open
- cancel and result requests of an action client

The wrappers expose only the send, wait and ready methods and a read-only `client()` accessor that returns the wrapped client, which serves anything else, such as cancel and result requests or removing a pending request.

With a multithreaded executor, callbacks can run while `handle_activate` is still executing, because the gate is already open.
State that they need must be ready by the end of `handle_configure`.
A callback that throws propagates out of the executor, and an active-only service leaves that request unanswered.

#### Active-only example

This example shows a hand-written (non-generated) node using the gate of `nodl_runtime_cpp::LifecycleNode` to gate a subscription, a service server and a client.
It doubles the numbers it receives, adds numbers on request and asks a peer to add numbers, and blocks all three while it is inactive.
Generated nodes with an `activation_gated` base class wrap their callbacks the same way.

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: using AddTwoInts
:end-before: int main
```

The example is compiled as part of the package tests.

## Background

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.
Sealing the transition callbacks and offering hooks instead makes that standard behavior impossible to skip.
Active-only entities add the same guarantee for subscriptions and services.
Without a gate, their callbacks run in every lifecycle state, so each callback would have to check the node state itself.
