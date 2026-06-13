# NoDL Concepts

NoDL (Node Definition Language) is not a single schema but a small family of JSON Schemas that describe a ROS 2 node's interface at increasing granularity:

- a **parameter definition** — a single ROS 2 parameter (type, default value, validation, ...), matching the shape used by [`generate_parameter_library`](https://github.com/pickNikRobotics/generate_parameter_library).
- an **interface definition** — a (possibly partial) node interface: parameters, topics, services, and actions.
- a **node definition** — a _whole_ node's interface, [composed](#composition) from interface definitions.

A NoDL file can be consumed:

1. at **runtime** by conformance testing and health monitoring
1. at **build time** by code generators
1. at **documentation time** to describe a node for its users

## Node identity

A NoDL interface definition does _not_ declare its own name, package, or namespace.
Those come from the containing ROS package and the file's location within it.
It describes interfaces, not identity.

## Node interfaces

NoDL defines the interface surface exposed by a ROS 2 node.
Those interfaces are:

- **Parameters** — typed, with optional default value, description, read-only flag, and validation rules.
- **Topic endpoints: Publishers and subscriptions** — name, type, and QoS profile.
- **Service endpoints: servers and clients** — name, type, and QoS profile.
- **Action endpoints: servers and clients** — name and type.

See the [schema reference](schema.md) for field-by-field detail.

## Composition

A single interface definition is often not the whole story: a node inherits interfaces from its ROS base type and may share reusable interfaces with other nodes.
A NoDL **node definition** composes a whole interface from three layers:

- **`base`** — a built-in ROS 2 node type (`node` or `lifecycle_node`) whose interface is inherited. It resolves to a built-in interface definition shipped with `nodl_schema` (e.g. `use_sim_time`, and for lifecycle nodes the state-management services and transition event).
- **`main`** — the interface this node's implementation _owns_, written in place as an interface definition.
- **`mixins`** — additional interface definitions merged in, each either a reference (`nodl://<package>/<name>` for an interface definition registered in the ament index, or a path relative to the node file) or an in-place interface definition.

Layers merge in order **base → mixins (as listed) → main**; later layers win on a name collision, so `main` always has the final say.

Mixins are single-level: a referenced interface definition is merged as-is and cannot itself declare a `base` or further `mixins`. The interface definition schema forbids those keys, so this is enforced, not just convention.

### Forward and backward

This split lines up with the two [usage models](#usage-models):

- Working **forward** (code generation), a generator implements `base` + `main` and **ignores `mixins`** — mixins describe interfaces owned by other code, not this node's implementation.
- Working **backward** (observation), `base` can be deduced and the full observed non-base interface placed in `main`. `mixins` cannot be deduced and are simply absent; conformance and documentation still work against the merged result.

## Syntax & Frontend(s)

The schema is JSON Schema.
By default, YAML and JSON files are accepted interchangeably as input; both deserialize to the same model.
Tools should not assume any particular extension (such as `.nodl.yaml`) or a single frontend.

## Validation

`ros2 nodl validate <file>` accepts any NoDL file and checks it against the matching schema, auto-detecting whether it is a parameter, interface, or node definition (`nodl_schema.load_nodl`); `load_parameter` / `load_interface` / `load_node` validate a known kind.

NoDL files are also validated at build time by the `ament_nodl` CMake macros, before install, so authoring errors surface during the build of the package that owns the file, not at runtime — a misconfigured node never ships.
The `ament_nodl` package registers files into the ament index and validates them as it does:

- `ament_nodl_register_node(<exe> FILE ...)` registers a node definition (under the `nodl_nodes` resource type) for an executable.
- `ament_nodl_register_interface(<name> FILE ...)` registers a reusable interface definition (under `nodl_interfaces`) that other nodes pull in as a mixin via `nodl://<package>/<name>`.

## Usage Models

The NoDL project aims to support two directional modes of use for NoDL definitions, which it calls "forward" and "backward".

### "NoDL Forward"

When working "NoDL forward", the definition serves as the source of truth that makes a node's interface exist.
The key workflow is:

1. Write a NoDL definition
1. Use code generation or dynamic runtime tooling to produce the defined interface

This model is targeted at development of new nodes, or migration of existing ones.

### "NoDL Backward"

When working "NoDL backward", the definition is the result of observing an existing node for the purposes of system validation and documentation.
The preexisting artifact is the source of truth, and the NoDL definition a reflection of it.

1. Run existing nodes or inspect their sources
1. Produce a NoDL description for its interfaces

This model enables drift detection, system analysis, and documentation generation for nodes that are not implemented NoDL-forward.
