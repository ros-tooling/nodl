# NoDL Schema reference

The following reference is generated from {repo}`nodl_schema/nodl_schema/schemas/nodl.schema.yaml`, which is the canonical source.

## Schema Version

The NoDL schema is [JSON Schema Draft 7](https://json-schema.org/draft-07).
This was chosen chosen to trivially support all live ROS 2 distributions - the key limitation being the system packages available on Ubuntu 22.04 Jammy with ROS 2 Humble.
After Humble EOL in May 2027, we will consider updating to a newer JSON Schema draft version.

## Node document

```{eval-rst}
.. json:schema:: Nodl
   :title: NoDL document
```

A node document references these shared types (generated from the schema's
`definitions`, see {repo}`nodl/doc/conf.py`):

```{eval-rst}
.. include:: _generated/schemas/nodl_definitions.txt
```

## Parameter schema

Parameters reference the subschema {repo}`nodl_schema/nodl_schema/schemas/parameter.schema.yaml`.
This is a formalization of the implicit schema defined by [`generate_parameter_library`](https://github.com/pickNikRobotics/generate_parameter_library) - NoDL builds on that work rather than reinventing the wheel.

```{eval-rst}
.. include:: _generated/schemas/parameter_definitions.txt
```
