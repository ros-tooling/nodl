# NoDL Concepts

A NoDL document declares a ROS 2 node's public interface.
It can be consumed:

1. at **runtime** by conformance testing and health monitoring
1. at **build time** by code generators
1. at **documentation time** to describe a node for its users

## Node identity

A NoDL document does _not_ declare its own name, package, or namespace.
Those come from the containing ROS package and the file's location within it.
The document describes interfaces, not identity.

## Node interfaces

NoDL defines the interface surface exposed by a ROS 2 node.
Those interfaces are:

- **Parameters** — typed, with optional default value, description, read-only flag, and validation rules.
- **Topic endpoints: Publishers and subscriptions** — name, type, and QoS profile.
- **Service endpoints: servers and clients** — name, type, and QoS profile.
- **Action endpoints: servers and clients** — name and type.

See the [schema reference](schema.md) for field-by-field detail.

## Syntax & Frontend(s)

The schema is JSON Schema.
By default, YAML and JSON files are accepted interchangeably as input; both deserialize to the same document model.
Tools should not assume any particular extension (such as `.nodl.yaml`) or a single frontend.

## Validation

NoDL files are validated both at build time (by the `ament_nodl` CMake macros, before install) and at runtime (by `nodl_schema.load_nodl`).
Authoring errors surface during the build of the package that owns the file, not at runtime, so a misconfigured node never ships.

## Usage Models

The NoDL project aims to support two directional modes of use for NoDL documents, which it calls "forward" and "backward".

### "NoDL Forward"

When working "NoDL forward", the document serves as the source of truth that makes a node's interface exist.
The key workflow is:

1. Write a NoDL definition
1. Use code generation or dynamic runtime tooling to produce the defined interface

This model is targeted at development of new nodes, or migration of existing ones.

### "NoDL Backward"

When working "NoDL backward", the document is the result of observing an existing node for the purposes of system validation and documentation.
The preexisting artifact is the source of truth, and the NoDL Document a reflection of it.

1. Run existing nodes or inspect their sources
1. Produce a NoDL description for its interfaces

This model enables drift detection, system analysis, and documentation generation for nodes that are not implemented NoDL-forward.
