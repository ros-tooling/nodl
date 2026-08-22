# ROS 2 basics: one NoDL contract, multiple bindings

Describe a conventional talker, specify its interface once as NoDL, then generate either C++ or Python bindings.
Application behavior remains ordinary ROS code.

> **Describe → Specify (NoDL) → Generate → Implement → Conform**

Choose C++ or Python in any language tab. The browser remembers that choice for the other grouped tabs on this page.

:::{note} Capability status
`describe` and `validate` work on NoDL `main`. Generation and conformance below show the intended workflow; they are
not implemented on `main` yet.
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

:::{warning} Draft workflow — not yet implemented
The commands and generated APIs in sections 3 through 5 show the intended product experience. They are not available
on NoDL `main`.
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

```cpp
class Talker : public generated::TalkerBase
{
public:
  Talker() : TalkerBase("talker")
  {
    timer_ = create_wall_timer(500ms, [this]() {on_timer();});
  }

private:
  void on_timer()
  {
    example_interfaces::msg::String message;
    message.data = "Hello World: " + std::to_string(count_++);
    pub_chatter_->publish(message);
  }

  size_t count_{0};
  rclcpp::TimerBase::SharedPtr timer_;
};
```

:::

:::{group-tab} Python

```python
class Talker(TalkerBase):
    def __init__(self):
        super().__init__('talker')
        self.count = 0
        self.timer = self.create_timer(0.5, self.on_timer)

    def on_timer(self):
        message = String(data=f'Hello World: {self.count}')
        self.pub_chatter.publish(message)
        self.count += 1
```

:::
::::

NoDL does not generate the timer period, counter, message contents, or logging in either language.

## 5. Conform a running implementation

:::{warning} Draft command — not yet implemented
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

For an intentional QoS regression, restart the talker with
`tutorial.publisher_reliability:=best_effort`, leaving the NoDL contract unchanged. Conformance should identify:

```text
[mismatch] publishers '/chatter'.qos.reliability
  expected: RELIABLE
  observed: BEST_EFFORT
```

Restore `RELIABLE` before the next run. Topic-name, durability, history, and depth variants follow the same pattern.
