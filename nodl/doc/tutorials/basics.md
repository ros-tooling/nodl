# ROS 2 basics: one NoDL contract, multiple bindings

Describe a conventional talker, curate its ROS interface once, then generate C++ or Python bindings without moving
application behavior into NoDL.

> **Describe → Curate → Generate → Implement → Conform**

Choose C++ or Python in any language tab. That choice stays synchronized across this page and is remembered by the
browser for other grouped language tabs in the same session.

:::{note} Capability status
`describe` and `validate` work on NoDL `main`. The later draft steps show the intended workflow for capabilities that
are not implemented yet.
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

`describe` creates a schema-valid NoDL draft. It filters common ROS infrastructure and preserves observable endpoint,
type, parameter, and QoS facts. If middleware discovery cannot recover a QoS field, the draft records that uncertainty
instead of inventing a value.

Stop the running talker before switching languages because every binding uses the node name `/talker`.

:::{admonition} Temporary review note: upstream QoS trivia
:class: note

At the pinned upstream revision, the C++ talker uses `KEEP_LAST` depth 7 while the Python talker uses depth 10. This
demonstrates the kind of difference discovery can reveal, but the tutorial does not depend on it. Remove this note
when the upstream examples align or the detail is no longer useful during review.
:::

## 2. Curate one contract

Decide what the talker interface should expose. The same contract will drive every generated binding. This tutorial
chooses depth 10 and makes every QoS requirement explicit:

```{literalinclude} ../../../examples/nodl_tutorial_verification/nodl/talker.nodl.yaml
:language: yaml
```

Validate the curated contract:

```bash
ros2 nodl validate examples/nodl_tutorial_verification/nodl/talker.nodl.yaml
```

The contract owns the publisher declaration. The timer, counter, log message, and `Hello World` contents remain
application behavior.

## 3. Generate a binding

:::{warning} Draft workflow — not yet implemented
Steps 3 through 5 show how generation, generated bindings, and conformance are intended to work. These commands and
APIs are not available on NoDL `main`.
:::

Use the same NoDL file regardless of language.

::::{tabs}
:::{group-tab} C++

```bash
ros2 nodl generate \
  examples/nodl_tutorial_verification/nodl/talker.nodl.yaml \
  --language cpp --output generated/cpp_talker
```

The generated C++ base exposes the declared publisher as `pub_chatter_`.
:::

:::{group-tab} Python

```bash
ros2 nodl generate \
  examples/nodl_tutorial_verification/nodl/talker.nodl.yaml \
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
#include <chrono>
#include <string>

#include "example_interfaces/msg/string.hpp"
#include "generated/cpp_talker/talker_base.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace std::chrono_literals;

class Talker : public generated::TalkerBase
{
public:
  Talker() : TalkerBase("talker"), count_(0)
  {
    timer_ = create_wall_timer(500ms, [this]() {on_timer();});
  }

private:
  void on_timer()
  {
    example_interfaces::msg::String message;
    message.data = "Hello World: " + std::to_string(count_++);
    RCLCPP_INFO(get_logger(), "Publishing: '%s'", message.data.c_str());
    pub_chatter_->publish(message);
  }

  size_t count_;
  rclcpp::TimerBase::SharedPtr timer_;
};
```

:::

:::{group-tab} Python

```python
from example_interfaces.msg import String
from generated.python_talker import TalkerBase


class Talker(TalkerBase):
    def __init__(self):
        super().__init__('talker')
        self.count = 0
        self.timer = self.create_timer(0.5, self.on_timer)

    def on_timer(self):
        message = String(data=f'Hello World: {self.count}')
        self.pub_chatter.publish(message)
        self.get_logger().info(f'Publishing: "{message.data}"')
        self.count += 1
```

:::
::::

NoDL does not generate the timer period, counter, message contents, or logging in either language.

## 5. Conform a running implementation

:::{warning} Draft command — not yet implemented
`ros2 nodl conform` is proposed tutorial UX. NoDL `main` does not provide this command yet.
:::

Build and start the selected implementation, then compare its observed interface with the same shared contract.

::::{tabs}
:::{group-tab} C++

```bash
colcon build --packages-select nodl_tutorial_cpp_talker
ros2 run nodl_tutorial_cpp_talker talker

# From another terminal
ros2 nodl conform /talker \
  --file examples/nodl_tutorial_verification/nodl/talker.nodl.yaml
```

After the conforming run, stop the node and launch the intentional QoS regression:

```bash
ros2 run nodl_tutorial_cpp_talker talker --ros-args \
  -p tutorial.publisher_reliability:=best_effort
```

:::

:::{group-tab} Python

```bash
colcon build --packages-select nodl_tutorial_python_talker
ros2 run nodl_tutorial_python_talker talker

# From another terminal
ros2 nodl conform /talker \
  --file examples/nodl_tutorial_verification/nodl/talker.nodl.yaml
```

After the conforming run, stop the node and launch the intentional QoS regression:

```bash
ros2 run nodl_tutorial_python_talker talker --ros-args \
  -p tutorial.publisher_reliability:=best_effort
```

:::
::::

Run conformance again. The semantic diff identifies the shared contract field rather than the implementation
language:

```text
[mismatch] publishers '/chatter'.qos.reliability
  expected: RELIABLE
  observed: BEST_EFFORT
```

Restore `RELIABLE` before the next run. Topic-name, durability, history, and depth variants follow the same pattern.
The [Dummy robot](dummy-robot.md) tutorial applies the complete regression set to a visible system.
