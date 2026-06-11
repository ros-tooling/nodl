# NoDL Schema reference

NoDL has two schemas, both generated below from their canonical sources:

- a **node definition** ({repo}`nodl_schema/nodl_schema/schemas/node.schema.yaml`) -- a whole-node composition of `base` + `mixins` + `main`.
- an **interface definition** ({repo}`nodl_schema/nodl_schema/schemas/interface.schema.yaml`) -- a (possibly partial) node interface, used for each composition layer.

See [Concepts](concepts.md#composition) for how the two relate.

## Schema Version

The NoDL schema is [JSON Schema Draft 7](https://json-schema.org/draft-07).
This was chosen chosen to trivially support all live ROS 2 distributions - the key limitation being the system packages available on Ubuntu 22.04 Jammy with ROS 2 Humble.
After Humble EOL in May 2027, we will consider updating to a newer JSON Schema draft version.

## Node composition

A node definition composes a whole interface from a built-in `base`, the node's own `main` interface, and zero or more `mixins`. `main` is an [interface definition](#interface-definition); each mixin is a reference (`nodl://<package>/<name>` or a relative path) or an in-place interface definition.

```{eval-rst}
.. json:schema:: Node
   :title: NoDL node definition
```

## Interface definition

```{eval-rst}
.. json:schema:: Interface
   :title: NoDL interface definition
```

An interface definition references these shared types (generated from the schema's
`definitions`, see {repo}`nodl/doc/conf.py`):

```{eval-rst}
.. include:: _generated/schemas/interface_definitions.txt
```

## Parameter schema

Parameters reference the subschema {repo}`nodl_schema/nodl_schema/schemas/parameter.schema.yaml`.
This is a formalization of the implicit schema defined by [`generate_parameter_library`](https://github.com/pickNikRobotics/generate_parameter_library) - NoDL builds on that work rather than reinventing the wheel.

```{eval-rst}
.. include:: _generated/schemas/parameter_definitions.txt
```
