# NoDL Schema reference

The NoDL schema is [JSON Schema Draft 7](https://json-schema.org/draft-07).
The following reference is generated from {repo}`nodl_schema/nodl_schema/schemas/nodl.schema.yaml`, which is the canonical source.

## Node document

```{eval-rst}
.. json:schema:: Nodl
   :title: NoDL document
```

A node document references these shared types:

```{eval-rst}
.. json:schema:: TopicEndpoint
.. json:schema:: ServiceEndpoint
.. json:schema:: ActionEndpoint
.. json:schema:: QosProfile
.. json:schema:: RosName
.. json:schema:: RosType
```

## Parameter schema

Parameters reference the subschema {repo}`nodl_schema/nodl_schema/schemas/parameter.schema.yaml`.
This is a formalization of the implicit schema defined by [`generate_parameter_library`](https://github.com/pickNikRobotics/generate_parameter_library) - NoDL builds on that work rather than reinventing the wheel.

```{eval-rst}
.. json:schema:: ParameterDefinition
.. json:schema:: ParameterType
.. json:schema:: ScalarType
.. json:schema:: ArrayType
.. json:schema:: FixedSizeType
.. json:schema:: DefaultValue
```

### Validation

```{eval-rst}
.. json:schema:: Validation
.. json:schema:: BoundsValidator
.. json:schema:: ComparisonValidator
.. json:schema:: SizeValidator
.. json:schema:: OneOfValidator
.. json:schema:: SubsetOfValidator
.. json:schema:: NoArgValidator
.. json:schema:: CustomValidator
```

## JSON Schema Version

JSON Schema Draft 7 is chosen to trivially support all live ROS 2 distributions - the key limitation being the system packages available on Ubuntu 22.04 Jammy with ROS 2 Humble.
After Humble EOL in May 2027, we may consider updating to a newer JSON Schema draft version.
