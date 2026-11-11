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

Lifecycle publishers registered with `add_managed_entity` follow the node state on every path with no author code, because the base class runs the standard activation and deactivation of `rclcpp_lifecycle::LifecycleNode` around the hooks.

#### Creating endpoints on activation

The base class keeps a registry of endpoints that exist only while the node is active.
Register them from the constructor of the authored class, with `manage` or `add_activation_slot`:

| Function | Registers |
|---|---|
| `manage(member, make)` | A `std::shared_ptr` member. `make` returns the endpoint at activation, and the member is reset at deactivation. |
| `manage_action_server<ActionT>(member, make)` | An action server member. `make` receives a `GoalTracker` and returns the server, and the active goals end before the server is reset. |
| `add_activation_slot(create, destroy)` | A pair of functions, for anything that is not a single member. `destroy` must be safe to call when `create` has not run. |

Slots are created in registration order when the node activates, and destroyed in reverse order when it deactivates, shuts down or errors.
Register the endpoints that others use first, such as publishers before the subscriptions that publish.
A `create` that throws destroys the slots created before it, and the transition fails with an error.
Registering while the node is activating or active throws `std::logic_error`.
A node that is destroyed while active destroys its members as usual, and `destroy` does not run.

A managed member is null while the node is not active, and the transition thread resets it, so a thread must not read it while a transition runs.
Where a member is safe to use:
- In the endpoint callbacks of the node, and in timers, that run in the default callback group.
  The default group is mutually exclusive, so these callbacks do not overlap the lifecycle services that request transitions.
- In every `handle_*` hook, which runs on the transition thread.

Where it is not:
- In a callback of a reentrant callback group or of a separate mutually exclusive group, which can run while a transition resets the member.
- In a thread of your own.
- In any callback when the transition is requested by calling `configure()`, `activate()` or `deactivate()` from a thread that is not the executor's, because that does not serialize with the default group either.

Stop that work in `handle_deactivate`, which runs before the endpoints are destroyed on deactivation, and on shutdown and error from the active state:
cancel the timers, and stop and join the threads.
Work that cannot be stopped from the hook, such as a callback in another callback group, takes a mutex of the authored class around every use of a member, and `handle_deactivate` takes the same mutex and sets a flag that the work checks before it uses the member.
Once the hook returns, no use of the member is in progress or starts.

| Transition | Order |
|---|---|
| configure | hook only |
| activate | create the slots, standard activation, then hook, and a result other than SUCCESS, or an exception, runs the standard deactivation and destroys the slots |
| deactivate | hook, then standard deactivation and slot destruction if the hook returned SUCCESS |
| cleanup | hook only |
| shutdown from active | `handle_deactivate`, destroy the slots, standard deactivation, then `handle_shutdown` |
| error from active | `handle_deactivate`, destroy the slots, standard deactivation, then `handle_error` |
| shutdown or error from unconfigured or inactive | hook only |

On shutdown and error from the active state `handle_deactivate` runs first, so the code that stops timers and threads there runs on every path that destroys the endpoints.
A shutdown cannot be vetoed, so a result other than SUCCESS from `handle_deactivate` on these paths is logged and ignored, and an exception from it is logged, and the endpoints are destroyed and the shutdown or error hook runs regardless.
An error that `handle_deactivate` caused by throwing does not run it again.
A failed or throwing `handle_activate` destroys the slots without running `handle_deactivate`, so the hook undoes its own partial work before it fails.

Destroying the slots does nothing when none is created, so a deactivation that already ran is not repeated by shutdown or error.
Configure and cleanup run only the hooks, so an entity registered with `add_managed_entity` does not receive them.
Only activation and deactivation reach managed entities, which includes the deactivation that runs on shutdown and error.

A hook that throws is turned into ERROR by `rclcpp_lifecycle`, which runs `on_error`.
When `handle_error` returns SUCCESS, the node ends unconfigured.

#### Ending action goals

A server registered with `manage_action_server` records the goals it accepts.
Pass `tracker.accepted(callback)` as its accepted callback, and the tracker records each goal before it calls `callback`.
When the node deactivates, shuts down or errors, every recorded goal that is still active ends with a default-constructed result, before the server is destroyed.
On deactivation that is after `handle_deactivate` has returned, so the hook can finish goals first:

| Goal state | Ends as |
|---|---|
| executing | aborted |
| deferred (accepted, not executing) | executed, then aborted |
| canceling | canceled |
| succeeded, aborted or canceled | left alone |

A goal accepted while the server is being destroyed ends the same way, and the accepted callback is not called.
A goal that finishes concurrently is skipped, and a call that throws while the goal is still active is retried once.
A worker thread of the node checks `goal_handle->is_active()` before it reports feedback or a result, and catches `rclcpp::exceptions::RCLError` from `succeed`, `abort`, `canceled` and `publish_feedback`, because the goal can end between the check and the call.
The goal handle throws that error once the goal has ended, and `end_all` itself never throws.

A client gets the result of an ended goal only when the server has already taken its result request off the wire.
When the node deactivates within a few milliseconds of the goal, the server is destroyed first and the request is never answered: with a result request followed at once by a deactivation, more than half of 200 trials left the client without a result, and none did when the deactivation came 20 ms later.
The status topic disappears with the server, so the client has no other signal.
A client uses a timeout on `async_get_result` and watches `action_server_is_ready()`.

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
- A request or goal that a managed client has sent and not yet received a response for fails with a `std::future_error` once the executor releases the client, which is shortly after `deactivate` returns.
- Each activation creates the endpoints again, with the discovery traffic that comes with it.
- An inactive node shows none of its registered endpoints in the graph.
  The destroyed endpoints leave the graph once the executor releases them: `deactivate` wakes the executors that wait on the node, and a node that no executor is spinning keeps them until its next spin.
- `LifecycleNode` wakes the executor with `trigger_notify_guard_condition()` from rclcpp 21 on, which covers Iron, Jazzy, Kilted and Rolling, and with `get_notify_guard_condition()` before that, which is Humble.
  Rolling removed `get_notify_guard_condition()`.

## Background

`rclcpp_lifecycle::LifecycleNode` activates its lifecycle publishers and other managed entities in its default `on_activate`, and deactivates them in `on_deactivate`.
A subclass that overrides those callbacks without calling the base class leaves them inactive.
Sealing the transition callbacks and offering hooks instead makes that standard behavior impossible to skip.

`rclcpp_lifecycle` has a lifecycle publisher and no lifecycle subscription, service, client or action type.
An entity created in the constructor is matched by the middleware and runs its callbacks in every state.
A `transient_local` subscription takes the publisher's history once, as soon as it matches, which is before the node is configured, and that sample is never delivered again.
Creating the endpoints at activation delivers it then, and matches the lifecycle design, in which an inactive node does not read topics.
