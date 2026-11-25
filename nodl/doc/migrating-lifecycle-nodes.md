# Migrating a handwritten lifecycle node

A handwritten lifecycle node derives `rclcpp_lifecycle::LifecycleNode` or `rclpy.lifecycle.LifecycleNode` and creates its own endpoints.
A NoDL lifecycle node declares its endpoints in a NoDL document, and its authored class derives the generated base class.
The generated base creates the endpoints and manages them across the lifecycle transitions.
The authored class keeps only the behavior that is specific to the node.

This page lists what changes when a handwritten lifecycle node moves to that form, in the order to do it.
The examples are a greeter node in each language, handwritten and migrated.
They are built and run in CI, with the same transitions applied to all of them.

## Checklist

1. Declare the node's interface in a NoDL document that includes `nodl://nodl_common_interfaces/lifecycle_node`.
1. Derive the generated base class, and delete the code that creates endpoints and declares parameters.
1. Rename each `on_*` transition callback to the matching `handle_*` hook, and delete the calls to the superclass.
1. Move code that relied on an incoming endpoint existing while the node is inactive.
1. Check the result of `get()` before each use of a service client or an action client.
1. Run the conformance test.

## Declare the interface

Describe the node's publishers, subscriptions, services, actions and parameters in a NoDL document, with the QoS settings the node uses.
Include `nodl://nodl_common_interfaces/lifecycle_node` to select the lifecycle base class.
The generators read its `lifecycle: true` metadata, and generate the lifecycle management of the endpoints.
Do not include it together with `nodl://nodl_common_interfaces/node`, because a document with two base classes is rejected.

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/nodl/greeter.nodl.yaml
:language: yaml
```

The package that generates C++ declares `nodl_runtime_cpp` as a dependency, because the generated base derives `nodl_runtime_cpp::LifecycleNode`.
The package that generates Python declares `nodl_runtime_py` as an `exec_depend`.
See the {doc}`nodl_generator_cpp <_generated/packages/nodl_generator_cpp/overview>` and {doc}`nodl_generator_py <_generated/packages/nodl_generator_py/overview>` pages for the CMake macros.
An `ament_python` package cannot call the CMake macro, and opts in from `setup.py` with `nodl_generate_py()` and `nodl_cmdclass()`, which the `nodl_generator_py` page describes under "ament_python integration".

## Derive the generated base class

The generated base class takes the node name from the generation target, without a trailing `_base`.
The C++ base class constructor takes `rclcpp::NodeOptions`, and the Python one takes keyword arguments for the `rclpy` base class.
The authored class uses the generated members in place of the ones the handwritten class named itself, so rename each use.
In C++ they are protected `pub_<name>_` and `cli_<name>_` (`action_cli_<name>_` for an action client), and the private `sub_<name>_` and `srv_<name>_`.
In Python they are `pub_<name>`, `cli_<name>` and `action_cli_<name>`, and `sub_<name>` and `srv_<name>`, which only hold the endpoint.
The generator overviews list the members of each kind.
The authored class does not call `create_publisher`, `create_subscription`, `create_service`, `create_client` or `declare_parameter` for what the document declares.

The base class owns:

- The publishers, as lifecycle publishers that drop messages while the node is inactive.
- The subscriptions and service servers, which exist only while the node is active.
- The service clients and action clients, which are handed out only while the node is active.
- The parameters.
  They are declared in the constructor, so they exist in every state, and a second declaration of the same name by the authored class fails.
  They are read as `params_` in the authored class.
- The lifecycle services and the `transition_event` publisher.

The authored class implements the abstract `on_<name>` callback of each subscription and service server.
A subscription named `name` calls `on_name`.
The generated endpoints use the default callback group of the node, and the schema has no field for another group.

## Rename the transition callbacks

The base class implements the six transition callbacks `on_configure`, `on_activate`, `on_deactivate`, `on_cleanup`, `on_shutdown` and `on_error`, and the authored class cannot override them.
In C++ they are `final`, and an override does not compile.
In Python an `on_*` method raises `TypeError` when the class is defined, and the message names the hook to define instead.
Define the hook with the matching name:

| Handwritten | Authored class |
|---|---|
| `on_configure` | `handle_configure` |
| `on_activate` | `handle_activate` |
| `on_deactivate` | `handle_deactivate` |
| `on_cleanup` | `handle_cleanup` |
| `on_shutdown` | `handle_shutdown` |
| `on_error` | `handle_error` |

Each hook takes the previous state and returns a `CallbackReturn` (C++) or `TransitionCallbackReturn` (Python).
The hooks default to `SUCCESS`, so define only the ones the node needs.
In C++ the hooks are `protected` and take `const rclcpp_lifecycle::State &`.
In Python they take a `LifecycleState`.

Do not call the superclass transition callback from a hook.
A handwritten `on_activate` calls `LifecycleNode::on_activate` to activate the lifecycle publishers, and `on_deactivate` calls the deactivation to deactivate them.
The base class does this on every transition, and a hook contains only the node's own behavior.
The hook returns a result and the base class acts on it:

- `handle_activate` runs after the lifecycle publishers are active and the endpoints are created.
  A `FAILURE` result destroys the endpoints again and leaves the node inactive.
  An `ERROR` result or an exception also destroys them, then runs `handle_error`.
  `handle_deactivate` does not run in either case.
- `handle_deactivate` runs before the endpoints are destroyed and while the lifecycle publishers are still active, so it can publish a last message.
  A `FAILURE` result leaves the node active and keeps the endpoints.
  An `ERROR` result runs `handle_error`, which runs `handle_deactivate` once more first, and an exception runs `handle_error` without repeating it.
- Shutdown and error from the active state run `handle_deactivate` first, then the shutdown or error hook.
  Cleanup that the node does when it deactivates therefore runs on every path out of the active state, and does not need to be repeated in `handle_shutdown` and `handle_error`.
  The result of `handle_deactivate` on these paths is ignored, since a shutdown cannot be vetoed.
- A hook that throws or raises moves the node to the error processing, which runs `handle_error`.
  When `handle_error` returns `SUCCESS` the node ends unconfigured, and any other result finalizes it.
  With the default `handle_error`, which returns `SUCCESS`, a nodl lifecycle node ends unconfigured after an error, in C++ and in Python, because its `on_error` returns the result of `handle_error`.
  Define `handle_error` to return another result when the node should be finalized instead.

The `nodl_runtime_cpp` and `nodl_runtime_py` overviews give the order of every transition.

## Where each endpoint lives

| Endpoint | Handwritten | Generated lifecycle node |
|---|---|---|
| Publisher | Lifecycle publisher, created in the constructor | The same, a `rclcpp_lifecycle::LifecyclePublisher` or an `rclpy` lifecycle publisher, and `publish` drops while the node is inactive |
| Subscription | Created in the constructor or `on_configure` | A `Managed` member, created at activation and destroyed at deactivation |
| Service server | Created in the constructor or `on_configure` | A `Managed` member, created at activation and destroyed at deactivation |
| Service client | Created in the constructor | A `Gated` member, which `get()` returns only while the node is active |
| Action client | Created in the constructor | A `Gated` member, which `get()` returns only while the node is active |
| Action server | Created in the constructor | Created in the constructor, as before (see Limits below) |

### Subscriptions and service servers

A subscription or service server does not exist while the node is unconfigured or inactive.
It is absent from the graph, a message published to it is not received by a volatile subscription, and a service request sent to it is not served.
A `transient_local` subscription receives its latched messages after the node activates, and not before.
Move code that relied on receiving while the node is inactive, or in `on_configure`, to run on activation or later.
The example tests show it: the handwritten subscription exists after configure, and the migrated one exists only after activate.

Discovery of the new endpoint starts at activation, so a peer may take a moment to match it.

### Service clients and action clients

A client exists for the lifetime of the node, so it is discoverable and matches its server while the node is inactive.
`get()` returns the client while the node is active, and null (`nullptr` in C++, `None` in Python) otherwise.
Check the result at each use:

::::{tabs}
:::{group-tab} C++

```cpp
if (auto client = cli_notify_.get()) {
  client->async_send_request(std::make_shared<std_srvs::srv::Trigger::Request>());
}
```

:::

:::{group-tab} Python

```python
if (client := self.cli_notify.get()) is not None:
    client.call_async(Trigger.Request())
```

:::
::::

`get()` returns the client in `handle_activate` and `handle_deactivate`.
For a node that follows the other rules in this guide, `get()` is null when the call runs in `handle_configure` or `handle_cleanup`, in a thread that outlives deactivation, or in a callback that was already running when the node deactivated.
The example calls the client from `handle_configure` to show it, and its test asserts that no request is sent while the node is inactive.
Without the check, that call dereferences null in C++ and fails the transition in Python.
A call from `handle_activate` right after startup can be sent before discovery has matched the server and be lost, so call `wait_for_service` (`wait_for_server` for an action client) first, or call from a timer or a callback that runs later.
`wait_for_service` blocks the thread that runs the transition, so keep the timeout short.
A response to a call made while the node was active can arrive after the node deactivates, and runs its callback.

### Timers, threads and other entities

The base class does not manage a timer, a thread or any entity the authored class creates itself, except through `Managed`.
Create them in `handle_activate` and stop them in `handle_deactivate`, which runs on every path out of the active state.
Create them last in `handle_activate`, so that a failing hook leaves none of them running.
In Python destroy a timer with `destroy_timer`, because dropping the reference does not destroy it.

In C++ a `nodl_runtime_cpp::Managed` member can hold a timer, which the node creates at activation, before `handle_activate`, and destroys at deactivation.
A member or a mixin of the authored class declares it in its initializer with the node and a function that returns the entity:

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/cpp/greeter.cpp
:language: cpp
:dedent: 2
:start-at: nodl_runtime_cpp::Managed<
:end-at: }};
```

In Python `Managed(node, create, destroy)` takes the function that destroys the entity too, for example `Managed(self, lambda: self.create_timer(1.0, self._on_timer), self.destroy_timer)`.
Construct it in `__init__` after `super().__init__()`.
A `Managed` or `Gated` member cannot be constructed while the node is activating or active.

## Example

The handwritten node creates its subscription in `on_configure`, its timer in `on_activate`, and calls the superclass in each transition callback.
The migrated node implements the callback of its subscription and the hooks, and the base class does the rest.
Both examples end with `rclcpp::spin` or `rclpy.spin`, so that a test can drive the transitions.
A Python node started with `nodl_runtime_py.run_node(Greeter)` is configured and activated after construction with no external transition.

::::{tabs}
:::{group-tab} C++

Handwritten:

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/cpp/handwritten_greeter.cpp
:language: cpp
:start-at: class Greeter
```

Migrated:

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/cpp/greeter.cpp
:language: cpp
:start-at: class Greeter
```

:::

:::{group-tab} Python

Handwritten:

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/python/handwritten_greeter.py
:language: python
:start-at: class Greeter
:end-before: def main
```

Migrated:

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/python/greeter.py
:language: python
:start-at: class Greeter
:end-before: def main
```

:::
::::

The CMake file builds all four nodes, and registers the conformance tests of the migrated ones:

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/CMakeLists.txt
:language: cmake
:start-at: nodl_generate_cpp
:end-at: RENAME greeter_py)
```

## Test conformance

`nodl_add_conformance_test` configures and activates a node whose document declares the lifecycle services, so the endpoints created on activation are present when it compares the node with the document:

```{literalinclude} ../../examples/nodl_tutorials/lifecycle_migration/CMakeLists.txt
:language: cmake
:start-at: nodl_add_conformance_test(greeter_cpp_conformance
:end-at: NODL_FILE nodl/greeter.nodl.yaml)
```

Run the tests of the package, and read the result, with:

```bash
colcon test --packages-select <package>
colcon test-result --verbose
```

Pass `NODE_NAME` when the node name differs from the test name, as the generation target determines it here.
The `ros2 nodl conform` command does not change the state of a node, so bring the node to active first, for example with `ros2 lifecycle set`.
See the {doc}`ros2nodl conformance guide <_generated/packages/ros2nodl/conformance>`.

## Limits

- Action servers of a lifecycle node are not covered yet.
  They are created in the constructor and serve goals in every state.
  Their lifecycle management is tracked for C++ in [nodl issue 261](https://github.com/ros-tooling/nodl/issues/261) and for Python in [nodl issue 266](https://github.com/ros-tooling/nodl/issues/266).
- A message published while the node is inactive is lost to a volatile subscription, because the subscription does not exist yet.
- A client can receive a response after the node deactivates, because a call made while the node was active completes on its own schedule.
- Transitions that a thread requests by calling `activate()` or `deactivate()` in C++, or `trigger_activate()` or `trigger_deactivate()` in Python, directly are not serialized with callbacks.
  Request transitions through the lifecycle services instead.
  See the runtime overviews for the details.

## Migrating with an agent

The repository carries an agent skill, `migrate-lifecycle-node`, that follows the checklist above.
