# ros2nodl

`ros2nodl` is a `ros2cli` extension that adds a `ros2 nodl` command group for working with NoDL documents from the
command line.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.
For the Python API that backs this command, see the `nodl_schema` package.

## Commands

```{toctree}
:hidden:

describe
```

Running `ros2 nodl` with no verb prints help. The available verbs:

### `ros2 nodl validate [files...]`

Validate one or more NoDL documents against the NoDL schema.
With no arguments, it reads a document from standard input.

```bash
# Validate files
ros2 nodl validate my_node.nodl.yaml other_node.nodl.yaml

# Validate from stdin
cat my_node.nodl.yaml | ros2 nodl validate
```

The command exits non-zero and prints the validation error if a document does not conform to the schema,
so it composes cleanly into shell pipelines and CI checks.

### `ros2 nodl describe`

Create a NoDL draft from a running or captured ROS 2 node.

```console
ros2 nodl describe NODE_NAME [--from FILE] [--no-params]
                         [--include-ros-infra] [--fail-on-warnings]
                         [--timeout SEC] [-o OUT.{yaml,json}]
```

```console
ros2 nodl describe /ns/talker
ros2 nodl describe /ns/talker --from talker.mcap -o talker.json
```

See the [Describe guide](describe.md) for each option and the ROS-to-NoDL mapping.

## Relationship to other packages

`ros2 nodl validate` is a thin CLI wrapper over `nodl_schema`'s validator.
For programmatic validation or for building tools on top of the typed data model, depend on `nodl_schema` directly.
For registering a node's NoDL document with the ament index from a CMake package, see the `ament_nodl` package.
