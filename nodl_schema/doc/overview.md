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

If the document has an `include` list, each reference is resolved and merged in (see the Composition section below);
the returned document carries the combined interface and no `include`.
Pass `resolve=False` to parse the document exactly as authored, following nothing.

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

## Composition: the `include` key

A document can pull in the interface of other NoDL documents through a top-level `include` list.
Each entry is a reference that is resolved, validated, and merged into the including document when it is loaded:

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
`nodl://<package>/<name>` is the built-in form; it names a document registered by `ament_nodl_register_node` and
resolves through the ament index to the resource `nodl_nodes/<package>__<name>`.
The schema checks that a `ref` is a URI and nothing more, since which schemes work is decided at runtime by what is
registered, so an unhandled scheme is a resolution error rather than a schema error.
A bare or absolute filesystem path names no resolver and is rejected by the schema.

Includes are followed recursively.
The merge is strict: a name collision within any single category (two publishers named `/status`, two parameters named
`gain`, and so on) across the document and its includes is an error.
A publisher and a subscription may share a name, since they are different categories.
Include cycles are detected and rejected.
Resolution failures and collisions raise `CompositionError`.

### Adding a reference form

A `Resolver` pairs `handles(ref)`, which reports whether it recognizes a reference, with `resolve(ref)`, which returns
that document's text.
Registering one is the whole of adding a reference form; neither `load_nodl` nor `resolve_document` takes a resolver,
so a form becomes available to every load in the process rather than to callers that were handed one.

```python
from nodl_schema import register_resolver, resolver_registered


class HttpResolver:
    def handles(self, ref: str) -> bool:
        return ref.startswith('https://')

    def resolve(self, ref: str) -> str:
        return fetch(ref)


register_resolver(HttpResolver())  # for the rest of the process

with resolver_registered(HttpResolver()):  # or just for this block
    doc = load_nodl(source)
```

The registry searches most-recently-registered first, so a registration shadows one already handling the same
reference for as long as it stays in place.
`resolver_registered` removes it on the way out, including when the block raises.
That is how the test suite substitutes an in-memory resolver with no ament index present.

`default_registry()` exposes the registry itself, and `resolve_document(data)` exposes the merge directly for callers
working with plain dicts.

```python
from nodl_schema import AmentIndexResolver, CompositionError, ResolverRegistry, default_registry, resolve_document
```

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
