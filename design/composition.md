# NoDL composition: design overview

This describes how one NoDL document reuses the interface of another, at a high level.

## Goal

A node's interface is often assembled from shared, reusable pieces: a common telemetry surface, a standard lifecycle
interface, a fleet-wide diagnostics contract.
Composition lets a document declare those pieces by reference instead of copying them, and have them merged in when the
document is loaded.

This pass is deliberately small.
Earlier passes modelled composition as a layered `base` + `mixins` + `main` structure with a separate interface-vs-node
schema split; that is abandoned.
There is one document type, one new key, and one way to name a reference.

## The `include` key

A document may carry a top-level `include` list.
Each entry is an object with a required `ref`:

```yaml
nodl_version: 2
include:
  - ref: nodl://sensor_common/imu_driver
```

`ref` is a `<scheme>://<body>` URI whose scheme selects a resolver.
`nodl://<package>/<name>` is the only form this pass ships, resolved through the ament index as the resource
`nodl_nodes/<package>__<name>`, which is exactly what `ament_nodl_register_node` installs.
`<name>` is a registered name, so it contains no path separators.

The schema checks that a `ref` is a URI and stops there.
It deliberately does **not** constrain the scheme, because resolvers are registered at runtime (see below), so the set
of working schemes is not knowable when the schema is written.
A pattern enumerating schemes would be a second registry contradicting the first, and would reject any form a consumer
registers.
The body is likewise the resolver's business: `nodl://pkg` with no name is a resolver error, not a schema error, since
the schema has no way to make that judgement for an arbitrary scheme.

A bare or absolute path is still a schema error, since it names no resolver at all.
The trade is that an unhandled-but-well-formed reference such as `ftp://x` is caught when resolving rather than when
validating, so `--no-resolve` no longer catches it.
That is the price of an open resolver set, and it is worth paying: the alternative caps the feature at the forms we
happened to think of.

## Resolvers

One reference form is what this pass needs, but **it must remain possible to support others.**
Adding a form should mean registering another resolver, not reworking composition.

A `Resolver` answers two questions about a reference:

```python
class Resolver(Protocol):
    def handles(self, ref: str) -> bool: ...
    def resolve(self, ref: str) -> str: ...
```

`handles` reports whether this resolver recognizes the reference; `resolve` fetches it.
Splitting the two is what makes the set of forms open, because it lets something else hold several resolvers and pick
between them.

That something is `ResolverRegistry`.
There is one process-wide instance, holding `AmentIndexResolver` by default, and `resolve_document` consults it:

```python
text = default_registry().resolve(ref)
```

Registration is the whole interface for adding a form:

```python
with resolver_registered(MyResolver()):
    doc = load_nodl(source)
```

**Neither `load_nodl` nor `resolve_document` takes a resolver.**
An earlier pass threaded one down through both, and the only caller that ever passed it was the tests, which is the
signal that it was the wrong seam: a real consumer wanting a new form had to touch every layer in between, while the
argument bought nothing for anyone else.
Registering says the same thing once, at the point where it is known, and every load in the process picks it up.

The registry searches **most-recently-registered first**, so a registration shadows one already handling the same
reference for as long as it stays in place.
This is what lets a test stand in for the ament index without one being present, and `resolver_registered` scopes it to
a block, removing the resolver on the way out even if the block raises, so a registration cannot leak between tests.

`resolve` returns document *text* rather than a path.
An ament index resource is content, not a file the consumer is meant to locate, and a form that fetches from somewhere
other than a filesystem would have no path to return.
Text is the smaller contract, and everything downstream of the fetch works on it and never inspects the reference that
produced it, so a reference form is a fetch strategy and nothing more.
Deciding what a form costs, whether that is network access during a build, caching, or trust in a remote source, is then
a question about that form alone rather than a question about composition.

## What loading does

`load_nodl` validates the document against the schema, then, if it has includes, resolves them and returns a
`NodlDocument` whose interface is the merged result and whose `include` key is gone.
`load_nodl(..., resolve=False)` skips resolution and returns the document as authored.

Resolution, for each reference:

1. Fetch it through whichever registered `Resolver` handles it.
2. Validate the fetched document against the schema.
3. Resolve its own includes recursively.
4. Merge its entities into the accumulator.

Merging is **strict, error on collision.**
Within any single category (each of `parameters`, `publishers`, `subscriptions`, the service and action lists) a
duplicate name across the document and its includes is an error.
Different categories are independent, so a publisher and a subscription may share a topic name.
There is no override or last-wins rule yet; we start strict and will loosen only when a concrete use case argues for it.

Include **cycles are detected** by tracking the resolution stack and rejected with a clear error.
A note on the current limitation: because dedup is not performed across resolution paths, a diamond (two includes that
each pull in the same third document) surfaces as a collision rather than being merged once.
That is acceptable under the strict policy for now.

## Build-time validation

`ament_nodl_register_node` already validates a document at build time by running `python -m nodl_schema` on it, and that
path now resolves includes by default.
So registering a document also checks that its references resolve: a broken reference fails the build, next to the
schema check.
The macro itself is unchanged.

This has an ordering consequence.
Validation runs before the package is installed, so an included `nodl://<package>/<name>` must point at a package that
is already built and is a dependency of the registering one.
A document cannot resolve an include that points back into its own, not-yet-installed package at build time, though it
resolves fine at runtime, after install.
`--no-resolve` on the validator is the escape hatch for a schema-only check.

The `nodl://` form reads only the installed workspace, so validation stays offline and deterministic.
A future form that is neither is worth weighing against that, since build-time validation is where the cost of resolving
a reference is paid.

## Deferred: intra-package references

The ordering constraint above means a package cannot currently compose its own documents.
Splitting a shared telemetry surface out of two of a package's own nodes still requires either duplicating it or
publishing it through a separate package.

Closing that gap needs a reference form that reads the source tree, and that form brings its own problems: such a
reference is meaningless once the document is installed and read back out of the index as text with no location, so
registration would have to rewrite it into something a consumer can resolve.
That is a separate change with its own design, and it slots in as another registered resolver plus a step in the
registration macro.
The registry here is what it will attach to, and the schema no longer has to be reopened to admit its scheme.

## Code layout

- `nodl_schema/schemas/nodl.schema.yaml`: the `include` array and the `reference` definition, whose `ref` pattern
  checks URI shape only.
  `models.py` is regenerated from it.
- `nodl_schema/composition.py`: the `Resolver` protocol, `AmentIndexResolver`, `ResolverRegistry` with its process-wide
  instance and the `register_resolver` / `resolver_registered` entry points, and `resolve_document` (recursive fetch,
  validate, cycle detection, strict merge).
  `CompositionError` is the failure type.
- `nodl_schema/validator.py`: `load_nodl` gains a `resolve` keyword, and the CLI gains `--no-resolve`.
- `ros2nodl/verb/validate.py`: the same `--no-resolve` flag, so `ros2 nodl validate` matches the module CLI.
- Resolution is pluggable through the registry, so the merge and cycle logic are unit-tested against a fake resolver
  registered under its own `test://` scheme, needing no ament index. A separate end-to-end test in `test_ament_nodl`
  resolves a real `nodl://` reference through the installed index.
