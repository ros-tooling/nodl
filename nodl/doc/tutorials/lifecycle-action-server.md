# Tutorial 4: build a lifecycle action server in C++ and Python

Define a Fibonacci action once, generate a lifecycle base for either language, then add the application behavior.

> **Shared contract → Generated base → Lifecycle subclass → Conform**

Choose C++ or Python in any language tab.
The browser remembers the selection for the other grouped tabs on this page.

The handwritten subclasses keep the calculation and callback structure familiar from the official
[`examples_rclcpp_minimal_action_server`](https://github.com/ros2/examples/tree/rolling/rclcpp/actions/minimal_action_server)
and
[`examples_rclpy_minimal_action_server`](https://github.com/ros2/examples/tree/rolling/rclpy/actions/minimal_action_server).
No existing server is required; this tutorial starts from the interface contract.

## 1. Define one public action contract

Begin with the language-neutral public interface:

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/nodl/fibonacci.nodl.yaml
:language: yaml
```

Only this file is public and registered.
The shared lifecycle provider supplies both languages' base-class metadata and lifecycle interfaces.
It deliberately leaves the algorithm, feedback, cancellation, and inactive-state policy to the application.
The relative `fibonacci` name follows the upstream examples and remains namespace- and remap-friendly.
In the root namespace it appears as `/fibonacci` on the ROS graph.

## 2. Register the contract and generate a base

Choose one package: C++ or Python.
Each has its own complete `CMakeLists.txt` and builds independently using the shared `fibonacci.nodl.yaml`.
Its generator call both creates the base and registers the contract as the package's `fibonacci` resource.

:::::{tabs}
::::{group-tab} C++

**`cpp/CMakeLists.txt`** — the C++ build path, with its NoDL additions highlighted:

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/CMakeLists.txt
:language: cmake
:lines: 4-19
:lineno-match:
:emphasize-lines: 4-5,7-10,13
```

This generates a lifecycle node with `on_fibonacci_goal`, `on_fibonacci_cancel`, and `on_fibonacci_accepted`
callbacks.

:::{note}
:collapsible: closed
:title: Generated C++ base

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/test/expected/generated_cpp.txt
:language: cpp
```

:::

::::
::::{group-tab} Python

**`python/CMakeLists.txt`** — the Python build path, with its NoDL additions highlighted:

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/CMakeLists.txt
:language: cmake
:lines: 4-17
:lineno-match:
:emphasize-lines: 4-5,7-10
```

This generates a lifecycle node with `on_fibonacci_goal`, `on_fibonacci_cancel`, and `execute_fibonacci` callbacks.

:::{note}
:collapsible: closed
:title: Generated Python base

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/test/expected/generated_python.txt
:language: python
```

:::

::::
:::::

## 3. Implement behavior and lifecycle policy

Each complete server fits in one short source file:
{download}`C++ source <../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp>` or
{download}`Python source <../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py>`.
The excerpts below explain its three responsibilities, with line numbers matching the source.

### Gate goals with lifecycle state

Start inactive, open the gate only after activation succeeds, and close it before deactivation:

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp
:language: cpp
:lines: 87
:lineno-match:
```

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp
:language: cpp
:lines: 25-36
:lineno-match:
```

:::
:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py
:language: python
:lines: 19-30
:lineno-match:
```

:::
::::

### Decide whether to accept a goal or cancellation

Reject a goal while inactive and accept cancellation requests.
Limit the order to 0–46 so the sequence fits the action's 32-bit integers:

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp
:language: cpp
:start-at: rclcpp_action::GoalResponse on_fibonacci_goal(
:end-before: void on_fibonacci_accepted
:lineno-match:
```

:::
:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py
:language: python
:start-at: def on_fibonacci_goal
:end-before: def execute_fibonacci
:lineno-match:
```

:::
::::

### Execute the accepted goal

Calculate the sequence, publish feedback, observe cancellation, and return the result:

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp
:language: cpp
:start-at: void on_fibonacci_accepted
:end-before: std::atomic_bool active_
:lineno-match:
```

:::
:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py
:language: python
:start-at: def execute_fibonacci
:end-before: def main
:lineno-match:
```

:::
::::

The calculation, feedback, result, cancellation decision, and lifecycle gate all stay in the subclasses.

## 4. Understand the lifecycle boundary

![Configure moves from unconfigured to inactive; activate enables new goals. Deactivate closes the goal gate, and cleanup returns to unconfigured.](img/lifecycle-action-states.svg)

| Generated base/provider supplies | Handwritten subclass supplies |
| --- | --- |
| `LifecycleNode` inheritance, state machine, transition services, and default transition callbacks | The decision that new goals are accepted only while active |
| Construction and naming of the `/fibonacci` action server, discoverable in every lifecycle state | Goal validation, Fibonacci calculation, feedback, result, and cancellation behavior |
| The language-specific callback surface and action message plumbing | Activation and deactivation overrides that maintain the active gate |

New goals are accepted only while active.
Deactivation rejects new goals; accepted goals continue until completion or cancellation.

## 5. Run the lifecycle and action

### Build and start

Choose one implementation.
Both commands remap its node name to `/fibonacci_action_server`:

::::{tabs}
:::{group-tab} C++

```bash
colcon build --packages-up-to nodl_tutorial_lifecycle_action_cpp
source install/setup.bash
ros2 run nodl_tutorial_lifecycle_action_cpp fibonacci_action_server_cpp \
  --ros-args -r __node:=fibonacci_action_server
```

:::
:::{group-tab} Python

```bash
colcon build --packages-up-to nodl_tutorial_lifecycle_action_py
source install/setup.bash
ros2 run nodl_tutorial_lifecycle_action_py fibonacci_action_server_py \
  --ros-args -r __node:=fibonacci_action_server
```

:::
::::

### Configure, activate, and send a goal

In a second terminal, use the same commands for either language:

```bash
source install/setup.bash
ros2 lifecycle get /fibonacci_action_server
ros2 lifecycle set /fibonacci_action_server configure
ros2 lifecycle set /fibonacci_action_server activate
ros2 action send_goal --feedback /fibonacci example_interfaces/action/Fibonacci "{order: 5}"
```

### Deactivate, clean up, and check conformance

```bash
ros2 lifecycle set /fibonacci_action_server deactivate
ros2 lifecycle set /fibonacci_action_server cleanup
ros2 nodl conform /fibonacci_action_server \
  --file examples/nodl_tutorials/lifecycle_action/nodl/fibonacci.nodl.yaml
```

The result is `/fibonacci_action_server: conforms`.
Conformance checks the declared interface; runtime tests check lifecycle and action behavior.

:::{note}
:collapsible: closed
:title: Automated verification

CI tests each implementation independently with the documented node-name remap.
It checks registration, generated bases, lifecycle transitions, inactive and invalid goal rejection, feedback,
results, cancellation, and conformance without RViz, Gazebo, or Nav2.

:::
