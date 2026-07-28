# NoDL composition: design overview

This describes how one NoDL document reuses the interface of others, at a high level.

## Goal

A node's interface is often assembled from shared, reusable pieces: a common telemetry surface, a standard lifecycle
interface, a fleet-wide diagnostics contract.
Composition lets a document declare those pieces by reference instead of copying them, and have them merged in when the
document is loaded.

This pass is deliberately simple.
Earlier passes modelled composition as a layered `base` + `mixins` + `main` structure with a separate interface-vs-node
schema split; that is abandoned.
There is one document type, and one new key.

## The `include` key

A document may carry a top-level `include` list.
Each entry is an object with a required `ref`:

```yaml
nodl_version: 2
include:
  - ref: nodl://sensor_common/imu_driver
  - ref: https://example.com/shared/telemetry.nodl.yaml
```

`ref` is one of two forms:

- `nodl://<package>/<name>` resolves through the ament index to the document that `ament_nodl_register_node`
  publishes as the resource `nodl_nodes/<package>__<name>`.
  The macro installs the file itself into the index, so resolution is a direct `get_resource` lookup that returns the
  document text.
- `http://` / `https://` fetches the document over the network.

The schema constrains `ref` to those two schemes; anything else is a schema error, before resolution is even attempted.

## What loading does

`load_nodl` validates the document against the schema, then, if it has includes, resolves them and returns a
`NodlDocument` whose interface is the merged result and whose `include` key is gone.
`load_nodl(..., resolve=False)` skips resolution and returns the document as authored.

Resolution:

1. Fetch each `ref` through a `Resolver` (the default handles ament and http; tests inject their own).
2. Validate the fetched document against the schema.
3. Resolve its includes recursively.
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

`ament_nodl_register_node` already validates a document at build time by running `python -m nodl_schema` on it, and
that path now resolves includes by default.
So registering a document also checks that its references resolve: a broken `nodl://` or unreachable `http(s)://`
reference fails the build, next to the schema check.

This has an ordering consequence.
Validation runs before the package is installed, so an included `nodl://<package>/<name>` must point at a package that
is already built and is a dependency of the registering one.
A document cannot resolve an include that points back into its own, not-yet-installed package at build time (it
resolves fine at runtime, after install).
`http(s)://` references make the build perform network I/O; `--no-resolve` on the validator is the escape hatch for a
schema-only check.

## Code layout

- `nodl_schema/schemas/nodl.schema.yaml`: the `include` array and the `reference` definition (`ref` pattern).
  `models.py` is regenerated from it.
- `nodl_schema/composition.py`: the `Resolver` protocol, `DefaultResolver` (ament + http), and `resolve_document`
  (recursive fetch, validate, cycle detection, strict merge). `CompositionError` is the failure type.
- `nodl_schema/validator.py`: `load_nodl` gains `resolve` / `resolver`; the CLI gains `--no-resolve`.
- Resolution is pluggable so the merge and cycle logic are unit-tested with an in-memory fake resolver, with a
  separate end-to-end test resolving a real `nodl://` reference through the installed ament index.
