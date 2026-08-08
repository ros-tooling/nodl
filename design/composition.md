# NoDL composition: design overview

How one NoDL document reuses the interface of another.

## Goal

A node's interface is often assembled from shared pieces: a common telemetry surface, a standard lifecycle interface, a
fleet-wide diagnostics contract.
Composition lets a document declare those by reference instead of copying them, and have them merged in when the
document is loaded.

## The `include` key

A document may carry a top-level `include` list, where each entry is an object with a required `ref`:

```yaml
nodl_version: 2
include:
  - ref: nodl://sensor_common/imu_driver
```

`ref` is a `<scheme>://<body>` URI whose scheme selects a resolver.
`nodl://<package>/<name>` is the only form this pass ships, resolved through the ament index as the resource
`nodl_nodes/<package>__<name>`.

The schema checks that a `ref` is a URI and stops there.
It does not constrain the scheme, because resolvers are registered at runtime, so the set of working schemes is not
knowable when the schema is written.
The body is likewise the resolver's business: `nodl://pkg` with no name is a resolver error, not a schema error.

The trade is that a well-formed reference with an unhandled scheme is caught when resolving rather than when validating,
so a schema-only check does not catch it.
A bare or absolute path names no resolver and is still a schema error.

## Resolvers

A `Resolver` answers two questions about a reference:

```python
class Resolver(Protocol):
    def handles(self, ref: str) -> bool: ...
    def resolve(self, ref: str) -> str: ...
```

`handles` reports whether this resolver recognizes the reference; `resolve` fetches it.
Splitting the two lets the module hold several resolvers and pick between them, so adding a reference form is a
registration rather than a change to composition.

Resolvers are registered process-wide, and `resolver_registered` scopes a registration to a block, removing it on the
way out even if the block raises.
The most recently registered resolver that handles a reference wins, so a registration shadows an earlier one for the
same scheme.

`resolve` returns document text rather than a path, since a reference need not name anything on a filesystem.
Nothing downstream of the fetch inspects the reference that produced the text, so a reference form is a fetch strategy
and nothing more.

## What loading does

`load_nodl` validates the document, then resolves and merges its includes, returning a `NodlDocument` with no `include`
key.
`load_nodl(..., resolve=False)` returns the document as authored.

The two steps are separately available: `resolve_document` returns a document and everything it includes, and
`merge_documents` combines that list into one document.

Merging is **strict, error on collision.**
A duplicate name within any single category (each of `parameters`, `publishers`, `subscriptions`, the service and action
lists) is an error.
Categories are independent, so a publisher and a subscription may share a topic name.
There is no override or last-wins rule; we start strict and will loosen only when a use case argues for it.

Include **cycles are detected** and rejected.
Because dedup is not performed across resolution paths, a diamond (two includes that each pull in the same third
document) surfaces as a collision rather than being merged once.
That is acceptable under the strict policy for now.

## Build-time validation

Validating a document resolves its includes by default, so a broken reference is caught next to a schema error.

This has an ordering consequence.
Resolution reads the installed workspace, so a referenced package must already be built and be a dependency of the
referencing one.
A document cannot resolve an include pointing back into its own, not-yet-installed package at build time, though it
resolves fine at runtime after install.
`--no-resolve` is the escape hatch for a schema-only check.

The `nodl://` form reads only the installed workspace, so validation stays offline and deterministic.
A future form that is neither is worth weighing against that.

## Deferred: intra-package references

The ordering constraint above means a package cannot currently compose its own documents.
Splitting a shared telemetry surface out of two of a package's own nodes still requires either duplicating it or
publishing it through a separate package.

Closing that gap needs a reference form that reads the source tree.
Such a reference is meaningless once the document is installed and read back as text with no location, so registration
would have to rewrite it into something a consumer can resolve.
That is a separate change, and it slots in as another registered resolver plus a step in the registration macro.

## Code layout

- `nodl_schema/schemas/nodl.schema.yaml`: the `include` array and the `reference` definition, whose `ref` pattern checks
  URI shape only. `models.py` is regenerated from it.
- `nodl_schema/composition.py`: the `Resolver` protocol, resolver registration, and document merging.
  `ResolutionError` and `MergeError` are the failure types.
- `nodl_schema/ament_resolver.py`: `AmentIndexResolver`, which handles `nodl://`.
- `nodl_schema/loader.py`: `load_nodl` and `resolve_document`.
- Resolution is pluggable, so merge and cycle logic are unit-tested against a fake resolver registered under its own
  `test://` scheme, needing no ament index.
  A separate end-to-end test in `test_ament_nodl` resolves a real `nodl://` reference through the installed index.
