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

`ref` names a registered document in an already-installed package.
`nodl://<package>/<name>` is resolved through the ament index as the resource `nodl_nodes/<package>__<name>`, which is
exactly what `ament_nodl_register_node` installs.
`<name>` is a registered name, so it contains no path separators.

The schema constrains `ref` to that form, so anything else is a schema error before resolution is attempted.
A filesystem path is not a valid `ref`, absolute or relative: an absolute path cannot mean the same thing on two
machines, and a relative path is deliberately deferred (see below).

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
Splitting the two is what makes the set of forms open: resolving a reference becomes a matter of asking each registered
resolver whether it recognizes the form, and using the first that does.

This pass ships one resolver, `AmentIndexResolver`, which `handles` a reference by looking for the `nodl://` prefix and
`resolve`s it through the ament index.
There is no registry yet and nothing to loop over, so the call site is the direct form of what a registry would do:

```python
if resolver.handles(ref):
    text = resolver.resolve(ref)
```

Building the registry before there is a second resolver would be inventing a shape with nothing to fit it to.
The protocol is the part worth committing to now, because it is what a second form has to slot into.

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

1. Fetch it through a `Resolver`.
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
That is a separate change with its own design, and it slots in as another resolver plus a step in the registration
macro.
The `Resolver` protocol here is what it will attach to.

## Code layout

- `nodl_schema/schemas/nodl.schema.yaml`: the `include` array and the `reference` definition (`ref` pattern).
  `models.py` is regenerated from it.
- `nodl_schema/composition.py`: the `Resolver` protocol, `AmentIndexResolver`, and `resolve_document` (recursive fetch,
  validate, cycle detection, strict merge).
  `CompositionError` is the failure type.
- `nodl_schema/validator.py`: `load_nodl` gains `resolve` and `resolver` keywords, and the CLI gains `--no-resolve`.
- `ros2nodl/verb/validate.py`: the same `--no-resolve` flag, so `ros2 nodl validate` matches the module CLI.
- Resolution is pluggable, so the merge and cycle logic are unit-tested with an in-memory fake resolver, with a separate
  end-to-end test in `test_ament_nodl` resolving a real `nodl://` reference through the installed ament index.
