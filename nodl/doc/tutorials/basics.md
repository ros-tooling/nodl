# ROS 2 basics: one NoDL contract, multiple bindings

Describe a conventional talker, specify its interface once as NoDL, then generate either C++ or Python bindings.
Application behavior remains ordinary ROS code.

> **Describe → Specify (NoDL) → Generate → Implement → Conform**

Choose C++ or Python in any language tab. The browser remembers that choice for the other grouped tabs on this page.

:::{note} Capability status
`describe`, `validate`, and the underlying C++ generator work on NoDL `main`.
The unified generation command, Python generation, generated APIs, and conformance flow below show the intended
product experience and are not implemented on `main` yet.
:::

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

## 3. Generate a binding

:::{warning} Draft workflow: not yet implemented
The unified commands and generated APIs in sections 3 through 5 show the intended product experience.
The underlying C++ generator exists, but this complete cross-language workflow is not available on NoDL `main`.
:::

Use the same NoDL file regardless of language.

::::{tabs}
:::{group-tab} C++

```bash
ros2 nodl generate \
  examples/nodl_tutorials/basics/nodl/talker.nodl.yaml \
  --language cpp --output generated/cpp_talker
```

The generated C++ base exposes the declared publisher as `pub_chatter_`.

:::

:::{group-tab} Python

```bash
ros2 nodl generate \
  examples/nodl_tutorials/basics/nodl/talker.nodl.yaml \
  --language python --output generated/python_talker
```

The generated Python base exposes the same publisher as `pub_chatter`.

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

## 5. Test a running implementation for conformance

:::{warning} Draft command: not yet implemented
`ros2 nodl conform` is proposed tutorial UX. NoDL `main` does not provide this command yet.
:::

Build and start the selected implementation, then compare its observed interface with the shared contract.

::::{tabs}
:::{group-tab} C++

```bash
colcon build --packages-select nodl_tutorial_cpp_talker
ros2 run nodl_tutorial_cpp_talker talker
ros2 nodl conform /talker \
  --file examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

:::

:::{group-tab} Python

```bash
colcon build --packages-select nodl_tutorial_python_talker
ros2 run nodl_tutorial_python_talker talker
ros2 nodl conform /talker \
  --file examples/nodl_tutorials/basics/nodl/talker.nodl.yaml
```

:::
::::

For an intentional QoS regression, first ensure that the generated publisher enables ROS QoS overrides.
Then restart the talker with the ROS parameter
`qos_overrides./chatter.publisher.reliability:=best_effort`, leaving the NoDL contract unchanged.
Conformance should identify:

```text
[mismatch] publishers '/chatter'.qos.reliability
  expected: RELIABLE
  observed: BEST_EFFORT
```

Restore `RELIABLE` before the next run. Topic-name, durability, history, and depth variants follow the same pattern.

This regression is a target acceptance case, not an executable fixture in this PR.
Before the command is presented as runnable, CI must start the generated node, verify its observed publisher QoS, and
assert the expected conformance failure on each supported ROS and RMW combination.
