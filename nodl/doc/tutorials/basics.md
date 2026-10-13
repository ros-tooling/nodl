# ROS 2 basics: one NoDL contract, multiple bindings

Describe a conventional talker, specify its interface once as NoDL, then generate either C++ or Python bindings.
Application behavior remains ordinary ROS code.

> **Describe → Specify (NoDL) → Generate → Implement → Conform**

Choose C++ or Python in any language tab. The browser remembers that choice for the other grouped tabs on this page.

## 1. Describe the existing interface

Start one upstream talker and describe it from a second terminal.

::::{tabs}
:::{group-tab} C++

```bash
# Terminal 1
ros2 run demo_nodes_cpp talker

# Terminal 2
ros2 nodl describe /talker -o /tmp/cpp_talker.nodl.yaml
```

:::

:::{group-tab} Python

```bash
# Terminal 1
ros2 run demo_nodes_py talker

# Terminal 2
ros2 nodl describe /talker -o /tmp/python_talker.nodl.yaml
```

:::
::::

`describe` creates a schema-valid NoDL draft. It records observable endpoints, types, parameters, and QoS facts. If
middleware discovery cannot recover a QoS field, the draft records that uncertainty instead of inventing a value.

Stop the running talker before switching languages because both examples use `/talker`.

## 2. Specify the NoDL contract

Review the discovered draft and decide what the talker interface should expose. The same contract drives every
generated binding and conformance check:

```{literalinclude} ../../../examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
:language: yaml
```

Validate the contract:

```bash
ros2 nodl validate examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

The contract owns the publisher declaration. The timer, counter, log message, and `Hello World` contents remain
application behavior.

## 3. Register and generate in the package build

Keep NoDL validation, registration, generation, and installation in the package build.
Use the same NoDL contract regardless of language.

::::{tabs}
:::{group-tab} C++

Add the contract and C++ generator to the package's `CMakeLists.txt`:

```{literalinclude} ../../../examples/nodl_tutorials/basics/CMakeLists.txt
:language: cmake
:start-at: find_package(ament_nodl REQUIRED)
:end-at: DESTINATION lib/${PROJECT_NAME})
```

`ament_nodl_register()` validates the public contract and registers it in the ament index as `talker`.

`nodl_generate_cpp()` generates the C++ base class in a library target and rebuilds it when the contract changes.
Its input is a composition document that adds the base class to the contract through `local://talker.nodl.yaml`.

`nodl_generate_cpp()` also registers that document, under the name given by `RESOURCE_NAME`.
Without `RESOURCE_NAME`, it registers under the target name.
The index then holds two documents, the shared contract `talker` and the full C++ node description `talker_cpp`.

The contract must be registered in the same package, because the composition document includes it with `local://`.
Pass `NO_INDEX` instead to skip registering the composition document.

Build and source the package:

```bash
colcon build --packages-select nodl_tutorial_basics
source install/setup.bash
```

The generated C++ base exposes the declared publisher as `pub_chatter_`.
The generated header is included as `nodl_tutorial_basics/talker_base.hpp`.

```{admonition} Library options
:collapsible: closed

The library type follows `BUILD_SHARED_LIBS`; when it is unset, the library is static.
Pass `SHARED` or `STATIC` to `nodl_generate_cpp()` to choose the type explicitly.

The generated library target is private to the package.
To let other packages use it, pass `EXPORT` as described in {ref}`using-a-generated-target`.
```

:::

:::{group-tab} Python

```cmake
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_py REQUIRED)

ament_nodl_register(talker FILE nodl/talker.nodl.yaml)
# The contract is already registered as talker.
nodl_generate_py(talker_py_base nodl/talker.nodl.yaml NO_INDEX)

install(PROGRAMS python/talker.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME talker)
```

```bash
colcon build --packages-select nodl_tutorial_basics
source install/setup.bash
```

`ament_nodl_register()` registers the contract in the ament index as `talker`.
`nodl_generate_py()` would register its input document too.
Here that document is the contract, which is already registered, so the call passes `NO_INDEX`.
The generated Python base exposes the declared publisher as `pub_chatter`.
The `_py` segment keeps its CMake target distinct from the C++ target in this combined tutorial.
It also makes the default runtime node name `talker_py`, because the generator strips only the trailing `_base`.

:::
::::

## 4. Implement application behavior

Subclass the generated interface and keep the timer and message behavior in normal ROS code.

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/basics/cpp/talker.cpp
:language: cpp
```

:::

:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/basics/python/talker.py
:language: python
```

:::
::::

NoDL does not generate the timer period, counter, message contents, or logging in either language.

## 5. Check runtime conformance

Check that the running node matches the shared contract.

::::{tabs}
:::{group-tab} C++

Run the node in terminal 1 and the check in terminal 2:

```bash
# Terminal 1
ros2 run nodl_tutorial_basics talker_cpp

# Terminal 2
ros2 nodl conform /talker \
  --file examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

Expected: **`/talker: conforms`**.

:::

:::{group-tab} Python

Run the node in terminal 1 and the check in terminal 2:

```bash
# Terminal 1
ros2 run nodl_tutorial_basics talker

# Terminal 2
ros2 nodl conform /talker_py \
  --file examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

Expected: **`/talker_py: conforms`**.

:::

::::

To see how conformance detects topic, type, and QoS regressions, continue to [Test the Dummy robot for conformance](dummy-robot.md).

## 6. Automate conformance checks

Register a launch test to check the executable against the contract during `colcon test`.
Add the check inside `if(BUILD_TESTING)` in `CMakeLists.txt`:

::::{tabs}
:::{group-tab} C++

```{literalinclude} ../../../examples/nodl_tutorials/basics/CMakeLists.txt
:language: cmake
:start-at:   nodl_add_conformance_test(talker_cpp_conformance
:end-at:     NODL_FILE nodl/talker.nodl.yaml)
```

The test launches `talker_cpp` as `/talker_cpp_conformance` and compares it with the shared contract.

:::

:::{group-tab} Python

```{literalinclude} ../../../examples/nodl_tutorials/basics/CMakeLists.txt
:language: cmake
:start-at:   nodl_add_conformance_test(talker_py_conformance
:end-at:     NODL_FILE nodl/talker.nodl.yaml)
```

The test launches `talker` as `/talker_py_conformance` and compares it with the shared contract.

:::

::::

**Build and run the tests**

Use Cyclone DDS for these two tests so the conformance check can observe the contract's QoS history and depth.
Fast DDS on Humble and Jazzy does not expose these fields over discovery.
Add this setting after registering both tests, inside `if(BUILD_TESTING)`:

```{literalinclude} ../../../examples/nodl_tutorials/basics/CMakeLists.txt
:language: cmake
:start-at:   set_property(TEST talker_cpp_conformance talker_py_conformance APPEND PROPERTY
:end-at:     ENVIRONMENT "RMW_IMPLEMENTATION=rmw_cyclonedds_cpp")
```

The tutorial package already declares `rmw_cyclonedds_cpp` as a test dependency.

Stop manually launched tutorial nodes, then run these commands:

```bash
colcon build --packages-select nodl_tutorial_basics
source install/setup.bash
colcon test --packages-select nodl_tutorial_basics
colcon test-result --verbose
```

Both conformance checks should pass, and `colcon test-result` should report no errors or failures.

Example C++ test output:

```text
1/4 Test #1: talker_cpp_conformance ...........   Passed    4.35 sec
```

For nodes that need startup parameters, use `PARAMETERS` or `PARAMETERS_FILE` as described in the {doc}`ament_nodl guide <../_generated/packages/ament_nodl/overview>`.
For undeclared endpoints injected by the environment or temporarily excluded during adoption, see the {doc}`conformance ignore rules <../_generated/packages/ros2nodl/conformance>`.
