# nodl_generator_py

`nodl_generator_py` generates an `rclpy` base class from a NoDL document.
The generated class creates the declared ROS interfaces.
Application code subclasses it and implements only the node behavior.

Generated files are replaced whenever the `.nodl.yaml` input changes.
Handwritten application code remains separate from generated code.

NoDL and `nodl_generator_py` are build-time dependencies.
The installed generated module imports only normal ROS interfaces, `rclpy`, and the generated parameter module.
A deployed application therefore does not require NoDL or `nodl_generator_py`.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## CMake integration

The `nodl_generate_py()` CMake function is the primary user-facing API:

```cmake
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml)
```

For a project named `my_robot`, this generates and installs
`my_robot.generated.echo_node_base.EchoNodeBase`.
The target name must be a valid Python identifier.

### What the function does

| Step | What happens |
|---|---|
| Code generation | Creates the base module during the package build. |
| Build tracking | Regenerates when the NoDL input, generator, or template changes. |
| Build target | Creates an `ALL` custom target named `echo_node_base`. |
| Installation | Installs generated Python modules under `<project>.generated`. |
| Parameters | Delegates parameter-module generation to `generate_parameter_library_py`. |

The application package must declare `rclpy` and every generated ROS interface package as dependencies.
It needs `nodl_generator_py` only as a build-tool dependency.

### Arguments

| Argument | Description |
|---|---|
| `target` | Build target and generated module name. It is PascalCased directly for the class name, while a trailing `_base` is removed from the runtime node name. `echo_node_base` produces `EchoNodeBase`, running as `echo_node`. |
| `nodl_file` | Absolute path or path relative to the calling `CMakeLists.txt`. |

## Generated files

The generator produces these files in `<project>/generated`:

| File | When | Contents |
|---|---|---|
| `__init__.py` | Always | Marks the generated package. |
| `<target>.py` | Always | Generated `rclpy` base class. |
| `<target>_parameters.py` | With parameters | Typed parameter listener and values. |

When parameters are present, the build also creates an intermediate
`<target>_parameters.yaml` file for `generate_parameter_library_py`.
The intermediate YAML file is not installed.

## Example

Given this NoDL document:

```yaml
nodl_version: 2

parameters:
  greeting:
    type: string
    default_value: hello

publishers:
  - name: echo_out
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE

subscriptions:
  - name: echo_in
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE
```

Add the generator to the package's `CMakeLists.txt`:

```cmake
find_package(ament_cmake REQUIRED)
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml)

ament_package()
```

Keep behavior in a handwritten subclass:

```python
from my_robot.generated.echo_node_base import EchoNodeBase
from std_msgs.msg import String


class EchoNode(EchoNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(
            String(data=f'{self.params_.greeting}: {msg.data}')
        )
```

The generated base constructs the publisher, subscription, and parameter listener.
The subclass supplies the subscription callback and application behavior.

## Generated class API

Entity names become Python identifiers by removing leading and trailing `/` characters
and replacing other non-alphanumeric groups with `_`.

| NoDL entity | Generated member or callback | Subclass use |
|---|---|---|
| Publisher | `pub_<name>` | Publish messages. |
| Subscription | `sub_<name>` and abstract `on_<name>(msg)` | Implement the callback. |
| Service server | `srv_<name>` and abstract `on_<name>(request, response)` | Implement the callback. |
| Service client | `cli_<name>` | Send requests. |
| Action server | `action_srv_<name>` and abstract `execute_<name>(goal_handle)` | Implement goal execution. |
| Action client | `action_cli_<name>` | Send goals. |
| Parameters | `param_listener_` and `params_` | Read typed parameter values. |

The constructor accepts keyword arguments and forwards them to `rclpy.node.Node`.

## Parameters

NoDL parameters are converted to the YAML format consumed by
[`generate_parameter_library_py`](https://github.com/PickNikRobotics/generate_parameter_library).
The generated base obtains the initial typed values during construction:

```python
self.param_listener_ = echo_node_base_parameters.echo_node.ParamListener(self)
self.params_ = self.param_listener_.get_params()
```

## CLI reference

The CMake function calls the generator internally.
The same generator can be run directly for scripting or debugging:

```bash
python -m nodl_generator_py \
  --nodl-file nodl/echo_node.nodl.yaml \
  --output-dir generated/my_robot/generated \
  --target-name echo_node_base
```

| Flag | Description |
|---|---|
| `--nodl-file` | NoDL document to load. |
| `--output-dir` | Directory for generated files. It is created when absent. |
| `--target-name` | Generated module name. It must be a valid Python identifier. It becomes the class name directly; a trailing `_base` is removed from the runtime node name. |

## Current scope

This version supports parameters, publishers, subscriptions, services, actions,
and their available QoS settings in a flat NoDL document.

Documents with `include` entries are rejected.
Lifecycle nodes, include composition, and base-class discovery are not yet supported.

## Relationship to other packages

`nodl_schema` loads and validates the input document.
`nodl_generator_common` provides language-neutral entity naming.
`generate_parameter_library_py` generates typed parameter support when required.
The installed result uses `rclpy` and the ROS interface packages named by the document.
