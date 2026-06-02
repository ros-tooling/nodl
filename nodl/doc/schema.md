# NoDL Schema reference

The NoDL schema is [JSON Schema Draft 7](https://json-schema.org/draft-07).
The folloring reference is generated from {repo}`nodl_schema/nodl_schema/schemas/nodl.schema.yaml`, which is the canonical source.

```{jsonschema} ../../nodl_schema/nodl_schema/schemas/nodl.schema.yaml
```

## Parameter schema

Parameter definitions reference the subschema {repo}`nodl_schema/nodl_schema/schemas/parameter.schema.yaml`,

This is a formalization of the implicit schema defined by [`generate_parameter_library`](https://github.com/pickNikRobotics/generate_parameter_library) - NoDL builds on that work rather than reinventing the wheel.

```{jsonschema} ../../nodl_schema/nodl_schema/schemas/parameter.schema.yaml
```

## JSON Schema Version

JSON Schema Draft 7 is chosen to trivially support all live ROS 2 distributions - the key limitation being the system packages available on Ubuntu 22.04 Jammy with ROS 2 Humble.
After Humble EOL in May 2027, we may consider updating to a newer JSON Schema draft version.
