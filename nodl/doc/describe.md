# Describe

`ros2 nodl describe` turns a running or captured ROS 2 node into a NoDL draft.
It is the interpretation half of the backward workflow:

> Observe records everything; describe interprets it.

The `nodl_observe` backend captures `rosgraph_msgs/Node`. `describe` removes
runtime infrastructure, maps observed values into the NoDL schema, and validates
the result. The transform itself is deterministic and does not access the ROS
graph; file input still requires a sourced ROS environment to deserialize the
message.

## Usage

```console
ros2 nodl describe NODE_NAME [--from FILE] [--no-params] [--keep-hidden]
                             [--strict] [--raw] [--timeout SEC]
                             [--topic NAME] [-o OUT.{yaml,json}]
```

| Option | Effect |
|---|---|
| `--from FILE` | Read a captured `Node` from YAML or MCAP instead of observing live. |
| `--no-params` | Omit parameters and skip live parameter service calls. |
| `--keep-hidden` | Keep framework-created endpoints and parameters. |
| `--strict` | Return nonzero if a field cannot be recovered or validation fails. |
| `--raw` | Emit the captured `Node` rather than the NoDL document. |
| `--timeout SEC` | Set the live discovery timeout. |
| `--topic NAME` | Override the live observation topic. |
| `-o FILE` | Write YAML or JSON based on the filename extension. |

```console
ros2 nodl describe /ns/talker
ros2 nodl describe /ns/talker --from talker.mcap -o talker.json
```

## Mapping

Node identity is omitted because a NoDL document does not declare its own name.
Empty interface collections are also omitted.

Topics preserve their name and type. Their RMW QoS integers become NoDL enums:

| Policy | When observation reports `UNKNOWN` |
|---|---|
| `history`, `reliability` | `SYSTEM_DEFAULT` (required by the schema) |
| `durability`, `liveliness` | omitted |

`depth` is emitted only for `KEEP_LAST`. Finite durations become nanoseconds;
zero and the observation backend's infinite sentinel are omitted.

Services use `request_type.name` as their type. Response types and service QoS
are omitted because they add no representable runtime information.

Actions become one endpoint. Their type is recovered from the generated
`_SendGoal` or `_GetResult` service type; constituent services and topics are not
re-emitted.

Parameters are keyed by name. The descriptor supplies type, description,
constraints, read-only state, and range bounds. The observed value becomes the
default value when its type agrees with the descriptor.

## Infrastructure filtering

By default, `describe` removes framework-created interfaces:

- `/rosout` and `/parameter_events`
- parameter and type-description services
- `use_sim_time`, `start_type_description_service`, and `qos_overrides.*`

Endpoint filtering matches both name tail and type, so a user endpoint with the
same name but a different type remains. Use `--keep-hidden` to disable filtering.

## Drafts and limitations

When required data cannot be recovered, the command reports the affected field
on stderr. It emits the draft by default; `--strict` makes any such gap fatal.

Runtime observation cannot supply service QoS, descriptive prose, type hashes,
parameter `dynamic_typing`, or byte-array parameter values in the current NoDL
schema. Those values are omitted rather than guessed.

See [Concepts](concepts.md) for the backward workflow and [Schema](schema.md) for
the document format.
