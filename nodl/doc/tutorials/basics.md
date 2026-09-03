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

`ament_nodl_register()` validates the public contract and registers it in the ament index.
`nodl_generate_cpp()` generates the C++ base and rebuilds it when the contract changes.

Build and source the package:

```bash
colcon build --packages-select nodl_tutorial_basics
source install/setup.bash
```

The generated C++ base exposes the declared publisher as `pub_chatter_`.

:::

:::{group-tab} Python

```{warning}
Python generation is not yet implemented.
The CMake below shows the intended package-build integration and cannot be run yet.
```

```cmake
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_py REQUIRED)

ament_nodl_register(talker FILE nodl/talker.nodl.yaml)
nodl_generate_py(talker nodl/talker.nodl.yaml)
```

```bash
colcon build --packages-select nodl_tutorial_python_talker
source install/setup.bash
```

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

```{warning}
Python generation is not yet implemented.
The code below shows the intended generated API and cannot be run yet.
```

```{literalinclude} ../../../examples/nodl_tutorials/basics/python/talker.py
:language: python
```

:::
::::

NoDL does not generate the timer period, counter, message contents, or logging in either language.

## 5. Test a running implementation for conformance

Start the selected implementation, then compare its observed interface with the shared contract.

::::{tabs}
:::{group-tab} C++

```bash
# Terminal 1
ros2 run nodl_tutorial_basics talker_cpp
# Terminal 2
ros2 nodl conform /talker \
  --file examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

:::

:::{group-tab} Python

```{warning}
Python generation is not yet implemented.
The commands below show the intended workflow and cannot be run yet.
```

```bash
# Terminal 1
ros2 run nodl_tutorial_python_talker talker
# Terminal 2
ros2 nodl conform /talker \
  --file examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

:::
::::

The conforming result is:

```text
/talker: conforms
```

For an intentional regression, remap the generated publisher and leave the NoDL contract unchanged:

```bash
# Terminal 1
ros2 run nodl_tutorial_basics talker_cpp --ros-args -r chatter:=chatter_regressed
# Terminal 2
ros2 nodl conform /talker \
  --file examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

```text
[missing] publishers '/chatter': expected type 'example_interfaces/msg/String' was not observed
[extra] publishers '/chatter_regressed': observed undeclared type 'example_interfaces/msg/String'
```

Restart the talker without the remapping to restore conformance.
