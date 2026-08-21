# Tutorials

These tutorials use real ROS 2 projects to test both the current NoDL workflow and the workflow that later
capabilities must support. The pages progress from **Describe → Curate → Generate → Implement → Conform**, then
apply that workflow to a visible robot and framework-owned capabilities.

```{toctree}
:hidden:

basics
dummy-robot
nav2-controller
```

## Capability status

Every tutorial uses the same labels:

| Label | Meaning |
|---|---|
| **Main** | The command and behavior exist on the current NoDL `main` branch. |
| **Prototype** | A named implementation branch or commit exists and has an exercised feedback loop. |
| **Target** | The page defines intended usage and acceptance criteria; the capability is not on `main`. |

The current pages do not name a published prototype revision, so unsupported flows are labelled **Target**. A later
implementation PR should replace that label with **Prototype** and its branch or commit only after exercising the
documented fixture.

## The four-page journey

### 1. [ROS 2 basics: one NoDL contract, multiple bindings](basics.md)

Use **Main** to describe the existing talker interface. Curate one canonical `talker.nodl.yaml`, then follow how that
single contract drives multiple language bindings. Continue on the same page through the **Target** Python and C++
generation, behavior, and conformance flow.

### 2. [Dummy robot](dummy-robot.md)

Use **Main** to launch the full robot, describe `dummy_laser`, and curate and validate its contract. Continue through
the **Target** generation and conformance flow, including topic, type, and QoS regressions, then recover the working
robot in RViz.

### 3. [Nav2: C++ provider and Python client](nav2-controller.md)

Use the official TurtleBot 3 simulation to inspect a C++ `ControllerServer` and Python `BasicNavigator`. The
**Target** continuation composes provider bases and client capabilities while preserving endpoint ownership.

The index is the fourth page and the overview for the complete suite.

## Five-demo roadmap

| Tutorial | Upstream target | Documentation status | Adoption question |
|---|---|---|---|
| [ROS 2 basics](basics.md) | `ros2/demos`: `demo_nodes_cpp`, `demo_nodes_py` | Written; Main plus Target | Can one contract generate equivalent Python and C++ interfaces? |
| [Dummy robot](dummy-robot.md) | `ros2/demos`: `dummy_robot` | Written; Main plus Target | Can interface migration preserve a visible robot system? |
| Pendulum control | `ros2/demos`: `pendulum_control` | **TBD** | Can NoDL migrate interfaces without owning real-time behavior? |
| ros2_control | `ros2_control_demos`: Examples 1 through 17 | **TBD** | How do framework-provided diagnostics and status capabilities compose? |
| [Nav2](nav2-controller.md) | `navigation2`: C++ `ControllerServer` and Python `BasicNavigator` | Written; Target | Can composition identify provider bases and reusable client capabilities? |

<!-- TODO(nodl-tutorials):
Target: ros2/demos/pendulum_control, with separate pendulum_controller and pendulum_motor documents.
Prerequisites: advanced C++ endpoint bindings and logical-node registration for two nodes in one executable.
Proof: preserve RttExecutor, allocator, memory strategies, QoS, scheduling, timers, callbacks, and existing tests.
PR boundary: one ros2/demos implementation PR plus one NoDL tutorial and locked verification update.
-->

<!-- TODO(nodl-tutorials):
Target: ros-controls/ros2_control_demos Examples 1 and 17 as one progressive tutorial.
Prerequisites: fragments, logical-node registration, semantic diff, and conformance.
Proof: detect missing /diagnostics and /rrbot/hardware_status while retaining a separate NoDL document for
/rrbot_custom_status.
PR boundary: one ros2_control_demos implementation PR plus one NoDL tutorial and locked verification update.
-->

For a live presentation, use Dummy robot as the complete visual flow and Basics only as a short introduction. Keep
the framework examples as prepared scaling evidence. Conformance belongs inside each tutorial, not as a sixth demo.
