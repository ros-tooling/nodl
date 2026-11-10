# nodl_runtime_cpp

`nodl_runtime_cpp` provides shared utilities for C++ nodes, especially those that `nodl_generator_cpp` generates.
It provides `rclcpp_lifecycle` wrapper classes to enable a reusable pattern for consistently managing the state and behavior of entities in Lifecycle nodes, and `MutexProtected`, a value that is only reachable while holding its lock.

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

A lifecycle node has the ability to block subscription messages, service requests and client requests while it is inactive, and to end its action goals when it deactivates.
`active_only_subscription_callback`, `create_active_only_service`, `ActiveOnlyClient` and `ActiveOnlyActionClient` each put one entity behind the node's activation gate, and `ActiveOnlyActionServer` is a managed entity of its own.
The entity is still created in the constructor, as usual.

`nodl_runtime_cpp::LifecycleNode` owns the gate, a `nodl_runtime_cpp::Gate`, which is an alias of `rclcpp_lifecycle::SimpleManagedEntity`.
The standard activation opens it, before `handle_activate` runs, and the standard deactivation closes it, together with every lifecycle publisher.
Subclasses read it through the protected `gate()`, which returns a read-only `GatePtr`.
The helpers take the gate, not the node, so they also work with a gate that a non-generated `rclcpp_lifecycle::LifecycleNode` registers with `add_managed_entity` itself.

| Entity | Helper | While the gate is closed |
|---|---|---|
| Subscription | `active_only_subscription_callback` | The message is dropped and the callback is not called. |
| Service server | `create_active_only_service` | The request is dropped and no response is sent, so the client's request never completes. |
| Service client | `ActiveOnlyClient` | `async_send_request` throws `InactiveError`. |
| Action server | `ActiveOnlyActionServer` | New goals are rejected, and active goals end at deactivation. |
| Action client | `ActiveOnlyActionClient` | `async_send_goal` throws `InactiveError`. |

A client can send from `handle_activate`, where the gate is already open, and while the node is active.
It cannot send from `handle_configure`, so make requests that were made at configure time, such as fetching configuration from another node, from `handle_activate`.
These stay available while the gate is closed:

- waiting for a service or an action server, and checking whether it is ready, so `wait_for_service` works in `handle_configure`
- responses to requests sent while the gate was open
- cancel and result requests of an action client

The wrappers expose only the send, wait and ready methods and a read-only `client()` accessor that returns the wrapped client, which serves anything else, such as cancel and result requests or removing a pending request.

With a multithreaded executor, callbacks can run while `handle_activate` is still executing, because the gate is already open.
State that they need must be ready by the end of `handle_configure`.
A callback that throws propagates out of the executor, and an active-only service leaves that request unanswered.

#### Action goals at deactivation

A lifecycle node can reject action goals while it is inactive, and end its active goals when it deactivates.
`ActiveOnlyActionServer` provides this, as a managed entity with its own gate.
Create it in the constructor and register it with `add_managed_entity`, keeping it alive as for a lifecycle publisher.
It rejects goals until the node activates.
At deactivation it first becomes inactive, so no new goal is accepted, then ends every goal it accepted that is still active, with a default-constructed result:

| Goal state | Result |
|---|---|
| Accepted, from `ACCEPT_AND_DEFER` | `execute()`, then `abort()` |
| Executing | `abort()` |
| Canceling | `canceled()` |
| Terminal | skipped |

The Python `ActiveOnlyActionServer` sends the result that the execute callback returned instead.
A goal that reaches a terminal state while it is being ended makes the call throw, and the server skips that goal.
`handle_deactivate` runs before the standard deactivation, so a hook can finish goals itself, for example by succeeding them with a partial result.
On shutdown and error the standard deactivation, and so the ending of goals, runs before the hook.
A worker that keeps running for an ended goal must check `goal_handle->is_active()` and stop, because a terminal or feedback call that races the deactivation throws.

#### Active-only example

This example shows two hand-written (non-generated) nodes using `nodl_runtime_cpp::LifecycleNode` and its gate.
`Doubler` doubles the numbers it receives, adds numbers on request and asks a peer to add numbers, and blocks all three while it is inactive.
`Counter` serves an action, and ends its goals when it deactivates.
Generated nodes with an `activation_gated` base class wrap their endpoints the same way.

```{literalinclude} examples/lifecycle_node.cpp
:language: cpp
:start-at: using AddTwoInts
:end-before: int main
```

The example is compiled as part of the package tests.

### Mutex-protected values

`nodl_runtime_cpp::MutexProtected<T>` holds a `T` that can only be reached while holding its mutex.
`lock()` blocks until the mutex is free and returns a guard with `->` and `*` access, which releases the mutex when it is destroyed.
`lock() const` returns a guard with read-only access, so a `const` method can read the value.
The constructor takes a `T` to copy, or the arguments to construct it in place.
It is copied from `rosgraph_monitor/mutex_protected.hpp` in ros-tooling/graph-monitor.

Generated nodes with parameters hold their parameters in a `MutexProtected`.
This example, from the package tests, guards a value that is read from `const` methods and written from others:

```{literalinclude} ../test/test_mutex_protected.cpp
:language: cpp
:start-at: /// Holds a Value that only ever gets touched under the lock
:end-at: ProtectedValue value_;
```

Do not hold a guard across a blocking call, and copy a value out of the guard instead of keeping a reference to it.

### Parameter values

`nodl_runtime_cpp::values_equal(first, second)` compares two parameter values and treats NaN as equal to NaN, which `==` does not.
It compares the elements of vectors and arrays the same way.
Generated nodes use it to tell whether a parameter set changed a declared parameter.

## Background

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.
Sealing the transition callbacks and offering hooks instead makes that standard behavior impossible to skip.
Active-only entities add the same guarantee for subscriptions and services.
Without a gate, their callbacks run in every lifecycle state, so each callback would have to check the node state itself.
Clients throw instead of dropping a request that the gate refuses, because a dropped request would return a future that never completes.
An action server ends its goals at deactivation, because otherwise they would keep running, and keep their clients waiting, in a node that no longer does any work.
