# nodl_runtime_py

`nodl_runtime_py` provides shared utilities for Python nodes, especially those that `nodl_generator_py` generates.
It currently provides a lifecycle node base class that manages the state and behavior of a node's entities in a standard way, helpers that make subscriptions and services of a lifecycle node work only while it is active, and `run_node`, a main loop for `rclpy` nodes.

## What it provides

| Provides | For |
|---|---|
| `nodl_runtime_py.lifecycle.LifecycleNode` | A lifecycle node base class with standard transitions and optional hooks, described below. |
| `create_active_only_service`, `active_only_subscription_callback` | Subscriptions and services that work only while a lifecycle node is active, described below. |
| `run_node` | The main loop of an executable, described below. |
| `rclpy` | Generated base classes derive from `rclpy` node classes and create their entities. |
| `generate_parameter_library_py` | Generated parameter modules import its parameter validators. |

The dependencies may change as generated code changes, so depend on this package rather than on its contents.

## Using it with generated code

A package that generates Python nodes declares the generator as a build tool and this package as a runtime dependency,
the way message packages pair `rosidl_default_generators` with `rosidl_default_runtime`:

```xml
<buildtool_depend>nodl_generator_py</buildtool_depend>
<exec_depend>nodl_runtime_py</exec_depend>
```

`nodl_generate_py()` fails at configure time when the calling package does not declare it.

## Running a node

`run_node` is the main loop of an executable.
It constructs the node, spins it, and returns the process exit code.
An executable module returns it from `main()`, so a `console_scripts` entry point and running the module directly both exit with it:

```{literalinclude} examples/greeter.py
:language: python
:start-at: import sys
```

The node class is called with no arguments.
`run_node` returns 0, so the process exits with 0, when it receives SIGINT or SIGTERM, or when `rclpy.shutdown()` is called, from the node or from any thread.
A second signal restores the default behaviour, so a process stuck in a constructor, a callback or a shutdown can still be interrupted:
a second SIGINT raises `KeyboardInterrupt`, and a second SIGTERM terminates the process.
`run_node` installs signal handlers, so it must be called from the main thread, and raises `RuntimeError` otherwise.
The signal handlers that were installed before the call are restored when it returns.

### Lifecycle nodes

A lifecycle node is configured and activated after construction.
A transition that does not succeed raises a `RuntimeError` naming the node and the transition.
On exit the node is shut down, so that its `on_shutdown` callback runs.
This does not happen when `rclpy.shutdown()` was called first, because the transition cannot be published.

### Errors

Exceptions from the constructor, a lifecycle transition or a callback propagate to the caller, so the process exits with a traceback and a non-zero code.
Before they propagate, `run_node` shuts down the executor, shuts down a lifecycle node, destroys the node, and shuts down `rclpy`.
A cleanup step that fails does not skip the others.
When another error is propagating, the failures are logged.
Otherwise the first one is raised and any others are logged.

### Choosing the executor

Nodes are spun with a `SingleThreadedExecutor` by default.
Pass any executor class that takes no arguments as `executor_class`.
This executable reuses the `Greeter` example above:

```{literalinclude} examples/greeter_multithreaded.py
:language: python
:start-at: import sys
```

### Command line arguments

`run_node` passes `args` to `rclpy.init`, `sys.argv` by default, so ROS arguments such as `--ros-args -p greeting:=Goodbye` work as usual.
When passing `args`, put the program name first, as `sys.argv` does.

## Lifecycle node base class

`nodl_runtime_py.lifecycle.LifecycleNode` derives `rclpy.lifecycle.LifecycleNode` to provide a more opinionated and automated default behavior.
Generated lifecycle nodes derive it, and so can any other lifecycle node.

It implements the standard lifecycle methods `on_configure`, `on_activate`, `on_deactivate`, `on_cleanup`, `on_shutdown` and `on_error`, and they cannot be overridden.
A subclass that defines one of them raises `TypeError` when the class is defined.
Lifecycle publishers, and any other managed entity added with `add_managed_entity`, are activated and deactivated on every path, without author code.

A subclass adds behavior with optional hooks instead.
The hooks are `handle_configure`, `handle_activate`, `handle_deactivate`, `handle_cleanup`, `handle_shutdown` and `handle_error`.
Each takes the previous state and returns a `TransitionCallbackReturn`, SUCCESS by default.
A hook that raises makes the transition fail with ERROR, which runs `handle_error` after the standard deactivation.

This example shows a hand-written (non-generated) node using `nodl_runtime_py.lifecycle.LifecycleNode` to illustrate using the lifecycle hooks to add custom behavior on state transitions.
`run_node` configures, activates and shuts down it like any other lifecycle node.

```{literalinclude} examples/lifecycle_node.py
:language: python
:start-at: import sys
```

### Order of the hooks

The standard activation and deactivation are the `rclpy` defaults, which call the matching callback of every managed entity.
They run in this order around the hooks:

| Transition | Order |
|---|---|
| configure | hook |
| activate | standard activation, then hook. A result that is not SUCCESS runs the standard deactivation and is returned. |
| deactivate | hook, then standard deactivation. A result that is not SUCCESS is returned and the node stays active. |
| cleanup | hook |
| shutdown | standard deactivation, then hook |
| error | standard deactivation, then hook |

Publishers are therefore active during `handle_activate`, and inactive during `handle_shutdown` and `handle_error`.

### Background

`rclpy`'s default transition callbacks activate and deactivate managed entities only when an override remembers to call `super()`.
Sealing the callbacks means a node cannot skip that behavior by accident, and the hooks give authors a place for their own logic that needs no `super()` call.

Only activation and deactivation, including the deactivation on shutdown and error, reach managed entities.
A custom managed entity added with `add_managed_entity` does not receive configure or cleanup, and its `on_shutdown` and `on_error` are not called.
This matches the C++ base class, because `rclcpp_lifecycle` managed entities only have activate and deactivate callbacks.

## Active-only entities

`nodl_runtime_py.lifecycle.LifecycleNode` owns an activation gate, exposed read-only as `activation_gate`.
The gate is open while the node is active, and during `handle_activate`.
Two helpers take the gate, not the node, and make one entity work only while it is open:

| Entity | Helper | While the gate is closed |
|---|---|---|
| Subscription | `active_only_subscription_callback` | The message is dropped and the callback is not called. |
| Service server | `create_active_only_service` | The request is dropped and gets no response, so its client keeps waiting. |

Both accept coroutine function callbacks.
`create_active_only_service` takes the keyword arguments of `Node.create_service`, such as `qos_profile` or `callback_group`.
Generated lifecycle nodes use them for every subscription and service server.
Any node that owns a gate can use them, as in this example of a hand-written (non-generated) node using `nodl_runtime_py.lifecycle.LifecycleNode` to gate a subscription and a service on activation:

```{literalinclude} examples/active_only_node.py
:language: python
:start-at: class Calculator
:end-before: def main
```

With a multithreaded executor, callbacks can run while `handle_activate` is still executing.
State that they need must be ready by the end of `handle_configure`.

### Background

`rclpy` delivers subscription and service callbacks in every lifecycle state, and only publishers follow the lifecycle.
The gate is a `rclpy.lifecycle.SimpleManagedEntity` registered with `add_managed_entity`, so the standard activation opens it and the standard deactivation closes it, on every path that deactivates publishers.

`rclpy` always sends the value a service callback returns, and has no way to skip the response.
`create_active_only_service` therefore replaces `send_response` on the service instance.
This relies on the executor calling `service.send_response`, which the tests check on every supported distribution.
