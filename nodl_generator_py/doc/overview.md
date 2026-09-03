# Generate an `rclpy` base class

`nodl_generator_py` generates an `rclpy` base class at build time.
Application code subclasses it and implements the node behavior.

NoDL and `nodl_generator_py` are build-time dependencies.
The generated module imports normal ROS interfaces and `rclpy`, so deployed application code does not require NoDL.
Regeneration replaces only generated code, never the handwritten subclass.

This initial version supports publishers, subscriptions, and their QoS settings in a flat NoDL document.
It rejects documents with `include` entries.
Services, actions, parameters, lifecycle nodes, and composition-aware generation are not yet supported.

## Generate the base class

Add the generator to an `ament_cmake` or `ament_cmake_python` package:

```cmake
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(echo_node config/echo_node.nodl.yaml)
```

For a project named `my_robot`, this generates and installs
`my_robot._generated.echo_node.EchoNodeBase`.
The target name must be a valid Python identifier.

## Implement the node

Keep application behavior in a handwritten subclass:

```python
from my_robot._generated.echo_node import EchoNodeBase
from std_msgs.msg import String


class EchoNode(EchoNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(String(data=f'echo: {msg.data}'))
```

The generated base creates publishers and subscriptions.
Each subscription produces an abstract callback that the subclass implements.
