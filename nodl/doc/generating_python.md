# Generate an `rclpy` node

`nodl_generator_py` turns a NoDL document into an `rclpy` base class. The
generated class owns the ROS interfaces; application code subclasses it and
implements only the callbacks that contain node behaviour.

## Design principles

- NoDL and its generator are build-time dependencies. Generated nodes do not
  load or import NoDL at runtime.
- Generated base classes contain interface wiring; handwritten subclasses
  contain application behaviour and are never overwritten by regeneration.
- Generated code uses normal `rclpy` and ROS interface APIs so it can run
  without the generator installed.
- Python and C++ generation share the same NoDL semantics while keeping
  language-native APIs and packaging.
- Future composition is resolved before generation, without changing the
  subclassing model.

Packages may still install their NoDL documents for documentation or runtime
introspection, but generated nodes do not require those files to start.

## Describe the interface

For example, `config/echo_node.nodl.yaml` can describe an echo node:

```yaml
---
nodl_version: 2
publishers:
  - name: /echo_out
    type: std_msgs/msg/String
subscriptions:
  - name: /echo_in
    type: std_msgs/msg/String
```

## Generate the base class

An `ament_cmake` package can generate and install the Python module at build
time:

```cmake
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(echo_node config/echo_node.nodl.yaml)
```

The initial integration supports `ament_cmake` and `ament_cmake_python`
packages. It does not generate files into source trees from `setup.py`.

The target name must be a valid Python identifier. For a project named
`my_robot`, this generates `my_robot._generated.echo_node.EchoNodeBase`.

Pass `LIFECYCLE` to generate an `rclpy.lifecycle.LifecycleNode` base and use
lifecycle publishers:

```cmake
nodl_generate_py(echo_node config/echo_node.nodl.yaml LIFECYCLE)
```

## Implement the node

Keep application logic in a handwritten subclass:

```python
from my_robot._generated.echo_node import EchoNodeBase
from std_msgs.msg import String


class EchoNode(EchoNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(String(data=f'echo: {msg.data}'))
```

The generator creates publishers and clients as attributes. Subscriptions,
service servers, and action servers produce abstract callback methods that the
subclass must implement. The generated file starts with a warning not to edit
it; regenerate it from the NoDL source instead.

When the document declares parameters, the build also generates a typed
`<target>_params.py` module through `generate_parameter_library_py`. The base
class exposes its listener as `param_listener_` and the initial values as
`params_`.

QoS settings from the NoDL document are applied to generated publishers,
subscriptions, and services.
