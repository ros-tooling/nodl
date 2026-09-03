# nodl_schema

`nodl_schema` is the home of the canonical NoDL schema, plus a Python package that validates and compares NoDL documents.
It exposes a typed, in-memory data model for working with them.

For what a NoDL document means and what it declares, see {external+nodl:doc}`concepts`.
For the field-by-field schema reference, see {external+nodl:doc}`schema`.
This page documents the package's Python surface and how to use it.

## What it provides

- The canonical schema files at {repo}`nodl_schema/nodl_schema/schemas/nodl.schema.yaml`, shipped with the package.
- A validator that checks plain documents against that schema.
- A typed data model (`pydantic` models) so loaded documents are structured objects, not bare dicts.
- Include resolution for `nodl://` ament index resources and `local://` relative paths.
- Semantic comparison of two loaded documents.

## Python API

The public API is re-exported from the package root:

```python
from nodl_schema import load_nodl, dump_nodl, load_schema, validate
```

### `load_nodl(source, *, resolve=True) -> NodlDocument`

Load and validate a NoDL document from a string, bytes, or file-like object, returning a typed `NodlDocument`.
Raises a validation error if the document does not conform to the schema.

If `resolve=True`, each `include` reference is resolved and merged in (see [Composition](#composition)), returning a document with the full interface and no `include`.

```python
from nodl_schema import load_nodl

with open('my_node.nodl.yaml') as f:
    doc = load_nodl(f)

for name, parameter in (doc.parameters or {}).items():
    print(name, parameter.type)
```

### `validate(data) -> None`

Validate a plain `dict` against the NoDL JSON schema, raising on the first violation.
Use this when you already have parsed data and only need the conformance check, not the typed model.

### `dump_nodl(doc, *, format='yaml') -> str`

Serialize a `NodlDocument` (or a plain `dict`) back to a YAML or JSON string.
`None` fields are dropped and enums are unwrapped to their values, so the output round-trips through `load_nodl`.

### `load_schema() -> dict`

Load and cache the raw NoDL JSON schema as a `dict`, for tools that want to inspect the schema directly.

(composition)=
## Composition: the `include` key

A document can pull in the interface of other NoDL documents through a top-level `include` list.
Each entry is resolved, validated, and merged into the including document when it is loaded:

```yaml
nodl_version: 2
include:
  - ref: nodl://sensor_common/imu_driver
publishers:
  - name: /status
    type: std_msgs/msg/String
    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}
```

`ref` is a URI whose scheme selects the resolver that fetches the document.
`nodl://<package>/<name>` is the built-in form, resolved through the ament index.

Includes are followed recursively.
Double-inclusions of the same reference (including cycles) are rejected.
The same entity type with the same name declared twice is an error.
Resolution failures raise `ResolutionError`, and collisions raise `MergeError`.

## Code generation metadata: the `codegen` key

A document can carry an optional `codegen` field with opaque metadata for code generation tools.
The field is keyed by target language or tool (e.g. `cpp`, `python`). Each value is an object whose
contents are tool-defined and the NoDL schema does not constrain them:

```yaml
nodl_version: 2
codegen:
  cpp:
    role: base_class
    header: rclcpp/rclcpp.hpp
    class: rclcpp::Node

publishers:
  - name: /rosout
    type: rcl_interfaces/msg/Log
    qos: {history: KEEP_LAST, depth: 1000, reliability: RELIABLE}
```

`nodl_schema` validates that `codegen` is an object of objects, but does not inspect the contents.
Interpretation is left to the consuming code generation tool.

## Data model

The typed model lives in {repo}`nodl_schema/nodl_schema/models.py`.
`NodlDocument` is the document root; it holds the node's parameters and its topic, service, and action endpoints,
each as its own model (`ParameterDefinition`, `TopicEndpoint`, `ServiceEndpoint`, `ActionEndpoint`, `QosProfile`).
The interface concepts these models represent are described in {external+nodl:doc}`concepts`.

## Semantic comparison

The pure comparison API compares two loaded NoDL documents.
It does not load files, inspect running ROS nodes, or provide launch integration.

```python
from nodl_schema import diff

differences = diff(expected, actual, node_fqn='/robot/my_node')
```

`expected` and `actual` are `NodlDocument` objects.
An empty list means conformance.
Each `Difference` contains `kind`, `section`, `name`, and `detail`.
Supported kinds are `missing`, `extra`, `type_mismatch`, `qos_mismatch`, `property_mismatch`, and `unverifiable`.

### Interface rules

| Check | Rule |
|---|---|
| Membership | Missing declared interfaces and extra actual interfaces are differences. |
| Collections | Publishers, subscriptions, service servers, service clients, action servers, and action clients remain separate. |
| Names | `/status` stays absolute, `status` resolves in the node namespace, and `~/status` resolves below the full node name. |
| Types | A short type equals its kind-specific fully qualified form. For example, `std_msgs/String` equals `std_msgs/msg/String` for a topic. |
| Representation | Collection order and empty collections do not affect the result. |
| Ignored metadata | Description fields and top-level `codegen` metadata do not affect the result. |

### Quality of Service rules

| Check | Rule |
|---|---|
| Observability | Declared Quality of Service (QoS) that is not observable produces an `unverifiable` difference. |
| Optional policies | An omitted expected policy places no requirement on the actual endpoint. `SYSTEM_DEFAULT` and `BEST_AVAILABLE` accept a concrete actual policy. |
| Concrete policies | An unknown actual policy is `unverifiable`. Otherwise, the actual policy must match. |
| History and depth | `KEEP_LAST` requires a matching depth. Other history policies ignore depth. |
| Durations | Omitted and zero durations both mean unlimited. Finite nonzero durations must match exactly. |

### Parameter rules

| Check | Rule |
|---|---|
| Membership | Missing declared parameters and extra actual parameters are differences. |
| Type | Types must match. A generic actual type cannot prove a declared fixed-size type and produces `unverifiable`. |
| Read-only | A declared `read_only` value must match. An unknown actual value is `unverifiable`. |
| Ignored fields | Description, default value, additional constraints, validation rules, and the actual current value do not affect the result. |

`ros2nodl` loads and composes an expected document, describes a live node, and calls this API through `ros2 nodl conform`.
