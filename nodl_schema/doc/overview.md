# nodl_schema

`nodl_schema` is the home of the canonical NoDL schema, plus a Python package that validates NoDL documents and
exposes a typed, in-memory data model for working with them.

For what a NoDL document means and what it declares, see {external+nodl:doc}`concepts`.
For the field-by-field schema reference, see {external+nodl:doc}`schema`.
This page documents the package's Python surface and how to use it.

## What it provides

- The canonical schema files at {repo}`nodl_schema/nodl_schema/schemas/nodl.schema.yaml`, shipped with the package.
- A validator that checks plain documents against that schema.
- A typed data model (`pydantic` models) so loaded documents are structured objects, not bare dicts.
- A `python -m nodl_schema <file>` entry point for quick command-line validation.

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

## Data model

The typed model lives in {repo}`nodl_schema/nodl_schema/models.py`.
`NodlDocument` is the document root; it holds the node's parameters and its topic, service, and action endpoints,
each as its own model (`ParameterDefinition`, `TopicEndpoint`, `ServiceEndpoint`, `ActionEndpoint`, `QosProfile`).
The interface concepts these models represent are described in {external+nodl:doc}`concepts`.

## Command line

For one-off validation without writing code:

```bash
python -m nodl_schema my_node.nodl.yaml
```

For validation as part of a ROS 2 workflow, prefer the `ros2 nodl validate` command from the `ros2nodl` package.
