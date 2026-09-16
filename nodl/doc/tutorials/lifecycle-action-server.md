# Tutorial 4: build a lifecycle action server in C++ and Python

Define a Fibonacci action once, generate a lifecycle base for either language, then add the application behavior.

> **Shared contract → Generation document → Generated base → Lifecycle subclass → Conform**

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
It deliberately leaves the algorithm, feedback, cancellation, and inactive-state policy to the application.
The relative `fibonacci` name follows the upstream examples and remains namespace- and remap-friendly.
In the root namespace it appears as `/fibonacci` on the ROS graph.

## 2. Register the contract and generate a base

Register the public contract once:

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/CMakeLists.txt
:language: cmake
:start-at: ament_nodl_register(fibonacci
:end-at: ament_nodl_register(fibonacci
```

Add the shared lifecycle provider in one private generation document:

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/nodl/fibonacci_codegen.nodl.yaml
:language: yaml
```

The lifecycle provider contains both C++ and Python generation metadata, so both generators consume this same file.
The public contract remains independent of either client library.

Generate the selected base:

Use `NO_INDEX` for both generator calls to keep the generation document private.
Only the public Fibonacci contract is registered above.

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/CMakeLists.txt
:language: cmake
:start-at: nodl_generate_cpp(
:end-at: target_link_libraries(fibonacci_action_server_cpp PRIVATE fibonacci_action_server_cpp_base)
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

:::
:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/CMakeLists.txt
:language: cmake
:start-at: nodl_generate_py(
:end-at: RENAME fibonacci_action_server_py)
```

This generates a lifecycle node with `on_fibonacci_goal`, `on_fibonacci_cancel`, and `execute_fibonacci` callbacks.

:::{note}
:collapsible: closed
:title: Generated Python base

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/test/expected/generated_python.txt
:language: python
```

:::

:::
::::

## 3. Implement behavior and lifecycle policy

Build the subclass in three small pieces.

### Gate goals with lifecycle state

Start inactive, open the gate only after activation succeeds, and close it before deactivation:

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp
:language: cpp
:lines: 25-36,87
```

:::
:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py
:language: python
:lines: 19-30
```

:::
::::

### Decide whether to accept a goal or cancellation

Reject a goal while inactive and accept cancellation requests:

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp
:language: cpp
:start-at: rclcpp_action::GoalResponse on_fibonacci_goal(
:end-before: void on_fibonacci_accepted
```

:::
:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py
:language: python
:start-at: def on_fibonacci_goal
:end-before: def execute_fibonacci
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
```

:::
:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py
:language: python
:start-at: def execute_fibonacci
:end-before: def main
```

:::
::::

The calculation, feedback, result, cancellation decision, and lifecycle gate all stay in the subclasses.

::::{tabs}
:::{group-tab} C++

:::{note}
:collapsible: closed
:title: Complete C++ implementation

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/cpp/fibonacci_action_server.cpp
:language: cpp
```

:::

:::
:::{group-tab} Python

:::{note}
:collapsible: closed
:title: Complete Python implementation

```{literalinclude} ../../../examples/nodl_tutorials/lifecycle_action/python/fibonacci_action_server.py
:language: python
```

:::

:::
::::

## 4. Understand the lifecycle boundary

The ownership split is precise:

| Generated base/provider supplies | Handwritten subclass supplies |
| --- | --- |
| `LifecycleNode` inheritance, state machine, transition services, and default transition callbacks | The decision that new goals are accepted only while active |
| Construction and naming of the `/fibonacci` action server | Goal validation, Fibonacci calculation, feedback, result, and cancellation behavior |
| The language-specific callback surface and action message plumbing | Activation and deactivation overrides that maintain the active gate |

A ROS action server is not automatically lifecycle-managed.
The generated action server remains discoverable while the node is unconfigured or inactive.
Both subclasses start with a closed gate, open it after successful activation, and close it before deactivation.
Deactivation prevents new goals; an accepted goal continues until it succeeds or a client cancels it.
Cleanup needs no extra policy callback because it is reached from the already-inactive state.

## 5. Run the lifecycle and action

Build and source the package:

```bash
colcon build --packages-select nodl_tutorial_lifecycle_action
source install/setup.bash
```

Start one implementation:

::::{tabs}
:::{group-tab} C++

```bash
ros2 run nodl_tutorial_lifecycle_action fibonacci_action_server_cpp
```

The node name is `/fibonacci_action_server_cpp`.

:::
:::{group-tab} Python

```bash
ros2 run nodl_tutorial_lifecycle_action fibonacci_action_server_py
```

The node name is `/fibonacci_action_server_py`.

:::
::::

In a second terminal, set `NODE` to the selected name and exercise the lifecycle:

```bash
source install/setup.bash
NODE=/fibonacci_action_server_cpp  # use /fibonacci_action_server_py for Python

ros2 lifecycle get "$NODE"
ros2 lifecycle set "$NODE" configure
ros2 lifecycle set "$NODE" activate
```

Send a goal while active and display feedback:

```bash
ros2 action send_goal --feedback /fibonacci example_interfaces/action/Fibonacci "{order: 5}"
```

Then close the active gate and return to the unconfigured state:

```bash
ros2 lifecycle set "$NODE" deactivate
ros2 lifecycle set "$NODE" cleanup
```

A goal sent before activation or after deactivation is rejected by the subclass policy.
The fixture tests also cancel an in-progress goal and verify its canceled result.

Finally, compare the running server with its generation document in any lifecycle state.
The document resolves the public action contract plus the shared provider's observable lifecycle endpoints:

::::{tabs}
:::{group-tab} C++

```bash
ros2 nodl conform "$NODE" \
  --file examples/nodl_tutorials/lifecycle_action/nodl/fibonacci_codegen.nodl.yaml
```

The result is `/fibonacci_action_server_cpp: conforms`.

:::
:::{group-tab} Python

```bash
ros2 nodl conform "$NODE" \
  --file examples/nodl_tutorials/lifecycle_action/nodl/fibonacci_codegen.nodl.yaml
```

The result is `/fibonacci_action_server_py: conforms`.

:::
::::

The CI fixture uses only lifecycle services and an action client.
It tests registration, generated inheritance, transitions, inactive rejection, feedback, results, cancellation, and
conformance without RViz, Gazebo, or Nav2.
