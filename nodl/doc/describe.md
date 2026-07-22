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
ros2 nodl describe NODE_NAME [--from FILE] [--no-params]
                             [--include-ros-infra] [--fail-on-warnings]
                             [--timeout SEC] [-o OUT.{yaml,json}]
```

| Option | Effect |
|---|---|
| `--from FILE` | Read a captured `Node` from YAML or MCAP instead of observing live. |
| `--no-params` | Omit parameters and skip live parameter service calls. |
| `--include-ros-infra` | Include ROS-created endpoints and parameters. |
| `--fail-on-warnings` | Return nonzero if any field cannot be recovered. |
| `--timeout SEC` | Set the live discovery timeout. |
| `-o FILE` | Write YAML or JSON based on the filename extension. |

```console
ros2 nodl describe /ns/talker
ros2 nodl describe /ns/talker --from talker.mcap -o talker.json
```

## Mapping

The transform maps fields from `rosgraph_msgs/Node` into a NoDL document as
follows. Every output has `nodl_version: 2`; empty interface collections are
omitted.

### Topics

| `rosgraph_msgs/Node` input | NoDL YAML output | Rule |
|---|---|---|
| `publishers[].name` | `publishers[].name` | Copied. |
| `publishers[].type.name` | `publishers[].type` | Copied without the type hash. |
| `publishers[].qos.*` | `publishers[].qos.*` | Policies become NoDL enum names; finite durations become nanoseconds. |
| `subscriptions[]` | `subscriptions[]` | Uses the same topic mapping as publishers. |

### Services

| `rosgraph_msgs/Node` input | NoDL YAML output | Rule |
|---|---|---|
| `service_servers[].name` | `service_servers[].name` | Copied. |
| `service_servers[].request_type.name` | `service_servers[].type` | Used as the complete service type. |
| `service_clients[]` | `service_clients[]` | Uses the same service mapping as servers. |

### Actions

| `rosgraph_msgs/Node` input | NoDL YAML output | Rule |
|---|---|---|
| `action_servers[].name` | `action_servers[].name` | Copied. |
| `action_servers[].send_goal.request_type.name` | `action_servers[].type` | Removes the generated `_SendGoal` suffix; `_GetResult` is the fallback. |
| `action_clients[]` | `action_clients[]` | Uses the same action mapping as servers. |

### Parameters

| `rosgraph_msgs/Node` input | NoDL YAML output | Rule |
|---|---|---|
| `parameters[i].name` | `parameters.<name>` | Becomes the key in the parameter mapping. |
| `parameters[i].type` | `parameters.<name>.type` | Converted to the corresponding NoDL parameter type. |
| `parameter_values[i]` | `parameters.<name>.default_value` | Included when its type agrees with the descriptor. |
| `parameters[i].description` | `parameters.<name>.description` | Copied. |
| `parameters[i].additional_constraints` | `parameters.<name>.additional_constraints` | Copied. |
| `parameters[i].read_only` | `parameters.<name>.read_only` | Copied. |
| `parameters[i].*_range[0]` | `parameters.<name>.validation.bounds` | Lower and upper bounds are copied. |

### QoS mapping

RMW QoS integers become NoDL enum names:

| Policy | When observation reports `UNKNOWN` |
|---|---|
| `history`, `reliability` | `SYSTEM_DEFAULT` (required by the schema) |
| `durability`, `liveliness` | omitted |

`depth` is emitted only for `KEEP_LAST`. Finite durations become nanoseconds;
zero and the observation backend's infinite sentinel are omitted.

### Intentionally omitted fields

| `rosgraph_msgs/Node` input | Reason omitted |
|---|---|
| `name` | A NoDL document does not declare its own node name. |
| Endpoint `type.hash` | A NoDL endpoint type is represented by its name. |
| Service response type and QoS | A NoDL service endpoint stores the service type, not its generated request/response details. |
| Action constituent services and topics | They are collapsed into one NoDL action endpoint. |
| Parameter `dynamic_typing` | It is not represented by the current NoDL parameter model. |
| Byte-array parameter values | The current NoDL schema has no byte-array parameter type. |

## Infrastructure filtering

By default, `describe` removes framework-created interfaces:

- `/rosout` and `/parameter_events`
- parameter and type-description services
- `use_sim_time`, `start_type_description_service`, and `qos_overrides.*`

Endpoint filtering matches both name tail and type, so a user endpoint with the
same name but a different type remains. Use `--include-ros-infra` to disable
filtering.

See [Concepts](concepts.md) for the backward workflow and [Schema](schema.md) for
the document format.
