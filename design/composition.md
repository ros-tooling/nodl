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
  - ref: common/telemetry.nodl.yaml
```

`ref` is one of two forms:

- `nodl://<package>/<name>` names a registered document in an already-installed package, resolved through the ament
  index as the resource `nodl_nodes/<package>__<name>`.
- A relative path resolves against the directory of the document that contains the reference.
  It names a document in the same package, and it is the only form that can reference a document in the package
  currently being built.

The schema constrains `ref` to those two forms; anything else is a schema error, before resolution is even attempted.
An absolute filesystem path is not a valid `ref`, because it cannot mean the same thing on two machines.

Two forms are what this pass needs, but **it must remain possible to support other reference resolutions in the
future.**
Adding one should be a matter of teaching the resolver a new form, not reworking composition.
Two things keep that true: the `Resolver` protocol is a plain `ref -> text` function, so a form is a fetch strategy and
nothing more, and everything downstream of the fetch works on document text and never inspects the reference that
produced it.
Deciding what a reference form costs, whether that is network access during a build, caching, or trust in a remote
source, is then a question about that form alone rather than a question about composition.

## What loading does

`load_nodl` validates the document against the schema, then, if it has includes, resolves them and returns a
`NodlDocument` whose interface is the merged result and whose `include` key is gone.
`load_nodl(..., resolve=False)` skips resolution and returns the document as authored.

Resolution:

1. Normalize each `ref` against the **origin** of the document that contains it (see below).
   A relative path becomes an absolute `file://` ref at this step; a `nodl://` ref passes through unchanged.
2. Fetch the normalized `ref` through a `Resolver` (the default handles ament and file; tests inject their own).
3. Validate the fetched document against the schema.
4. Resolve its includes recursively, with the fetched document's own location as the new origin.
5. Merge its entities into the accumulator.

An **origin** is where a document was loaded from, and it is what a relative `ref` inside that document is relative to.
Normalizing before fetching keeps the `Resolver` protocol a plain `ref -> text` function, so a relative path never
reaches a resolver that would have no way to interpret it.
Normalizing also makes cycle detection correct: the resolution stack now holds absolute refs, so two different
spellings of the same file are recognized as the same document rather than recursing until something else breaks.

Only a document whose origin is a local file can carry a relative `ref`.
A relative reference inside a document fetched from the ament index is an error, because an index resource is text with
no location to be relative to.
That case should not arise in practice, because registration rewrites relative references before installing (see below).

Merging is **strict, error on collision.**
Within any single category (each of `parameters`, `publishers`, `subscriptions`, the service and action lists) a
duplicate name across the document and its includes is an error.
Different categories are independent, so a publisher and a subscription may share a topic name.
There is no override or last-wins rule yet; we start strict and will loosen only when a concrete use case argues for it.

Include **cycles are detected** by tracking the resolution stack and rejected with a clear error.
A note on the current limitation: because dedup is not performed across resolution paths, a diamond (two includes that
each pull in the same third document) surfaces as a collision rather than being merged once.
That is acceptable under the strict policy for now.

## Requirement: relative references must survive registration

A relative `ref` is resolvable in the source tree and meaningless outside it.
Registration has to close that gap, because `ament_nodl_register_node` publishes the document into the ament index and
a consumer in another package then reads it back with `get_resource('nodl_nodes', '<pkg>__<exe>')`.
That call returns the document *text* and nothing else.
There is no package name, no path, no origin of any kind attached to it, so a consumer that receives
`ref: common/telemetry.nodl.yaml` has nothing to resolve it against.

**The chosen resolution is that a relative reference is a private, intra-package spelling of a reference that is public
after install.**
A referenced document must already be registered in its own right, so it already has an index name and is already
installed.
Registration rewrites the reference in the installed copy from the relative path to the `nodl://<package>/<name>` that
names the same document, and nothing else changes.
A consumer never encounters a relative ref, so it never needs a base to resolve one.

Requiring prior registration is what keeps this small.
The alternative was for registration to publish referenced documents on their own initiative, which meant inventing an
index name for a document nobody had named, deciding where such a document installs, and making the install layout a
contract so the name could be resolved back to a file.
Requiring registration first means the name already exists, chosen by whoever registered it, so none of that is needed.

The other alternative was to inline the referenced entities and drop the reference, which also removes relative refs
from the installed artifact.
Rewriting is preferred because inlining answers "what is this node's interface" but destroys "what contracts does this
node implement," and the second question is most of the value of having composition at all.
Rewriting also keeps the installed document diffable against the authored one, since they differ only in the spelling of
each reference, and it stores a shared document once instead of copying it into every document that includes it.

Rewriting costs a runtime consideration in exchange: installed documents still carry references, so a consumer resolves
them at read time and the cycle detection and collision rules now matter after install, not only during the build.
That is already implemented and tested, so it is a shift in when the logic runs rather than new logic.

### Naming and ordering

Two rules make the rewrite unambiguous:

- **Registration order.**
  A document must be registered before any document that relatively includes it.
  `ament_nodl_register_node` records each registration for the current package, so a relative reference that resolves to
  an unregistered file is a configure-time error naming the file and asking for its registration to be moved above.
- **One name, one file.**
  Registering the same name twice for the same package from two different absolute files is a configure-time error.
  Without this a later registration would silently take over a name that an already-rewritten reference points at.

The rewrite looks the referenced document's absolute path up in that record and uses the name it was registered under.
In the normal case that name is the document's base name, so a reference to `common/telemetry.nodl.yaml` becomes
`nodl://<package>/telemetry` and reads the way the author wrote it.
Taking the name from the record rather than recomputing it from the base name costs nothing and removes a failure mode,
since a document registered under some other name still rewrites correctly instead of producing a reference to an index
entry that does not exist.

Two constraints that earlier drafts spelled out separately now come for free.
A reference cannot escape the package, because the record holds only this package's registrations and a file outside it
is simply not in the record.
Rewriting does not recurse, because each registered document is rewritten by its own registration call, so a document
that includes a document that includes a third one needs no special handling.

## Build-time validation

`ament_nodl_register_node` already validates a document at build time by running `python -m nodl_schema` on it, and
that path now resolves includes by default.
So registering a document also checks that its references resolve: a broken reference fails the build, next to the
schema check.

This has an ordering consequence.
Validation runs before the package is installed, so an included `nodl://<package>/<name>` must point at a package that
is already built and is a dependency of the registering one.
A document cannot resolve an include that points back into its own, not-yet-installed package at build time (it
resolves fine at runtime, after install).
`--no-resolve` on the validator is the escape hatch for a schema-only check.

Both current reference forms read only the local filesystem and the installed workspace, so validation is offline and
deterministic.
A future form that is neither is worth weighing against that, since build-time validation is where the cost of resolving
a reference is paid.

Relative references are the answer to that ordering constraint rather than another instance of it.
They resolve against the source tree, which is present at build time, so a package can finally compose its own
documents.
Splitting a shared telemetry surface out of two of a package's own nodes previously required either duplicating it or
publishing it through a separate package; a relative ref makes it a local file.

## What registration does

`ament_nodl_register_node` gains a rewrite step between validation and install, and records the registration:

1. **Record** this document's absolute path, name, and package, erroring if the name is already recorded against a
   different file.
   The record is a global CMake property, so it is visible to later calls wherever they appear in the project.
2. **Check** that every relative reference reachable from the document is already recorded, and fail configure naming
   the offending file if one is not.
   Doing this at configure time puts the error where the fix is, which is the ordering of calls in the `CMakeLists.txt`.
3. **Validate** the authored document with full resolution, as today.
   A broken reference fails the build.
4. **Rewrite** the document into the build directory, replacing each relative `ref` with the `nodl://<package>/<name>`
   its record entry gives and leaving `nodl://` entries untouched.
5. **Install** the rewritten document, as the `nodl_nodes` resource and into `share/<package>/nodl/`, exactly where the
   authored file went before.

A document with no relative references is passed through byte for byte, so registering one is unchanged by any of this.
Only a document that actually has a reference to rewrite is re-serialized, and then in the format its extension implies,
so a `.nodl.json` document stays JSON.
Such a document is no longer installed exactly as authored, which is the visible cost of the approach.
It is a small one: it differs from the authored file only in the spelling of its references, so the two remain readable
against each other, and the authored file stays in the source tree and in version control.

Dependency tracking uses the transitive set of relatively referenced files, not just the direct ones.
Validation resolves a relative reference from the source tree, and a referenced document's own relative references
resolve from the source tree too, so editing a document two levels down still changes what validation sees.
The macro asks `nodl_schema` for that set at configure time and adds it to the validation command's `DEPENDS` and to
`CMAKE_CONFIGURE_DEPENDS`.
Rewriting stays non-recursive regardless, since each document is rewritten by its own registration.

The `PACKAGE` override is carried through the record, so a document registered under a different package name rewrites
to a reference naming that package rather than the one being built.

## Code layout

- `nodl_schema/schemas/nodl.schema.yaml`: the `include` array and the `reference` definition (`ref` pattern).
  The pattern admits a `nodl://` URI or a relative path, and rejects a leading `/`.
  `models.py` is regenerated from it.
- `nodl_schema/composition.py`: the `Resolver` protocol, `DefaultResolver` (ament index and local file), and
  `resolve_document` (normalize against origin, recursive fetch, validate, cycle detection, strict merge).
  `resolve_document` takes an `origin` and threads each fetched document's location through the recursion.
  Two entry points serve registration: one reports the transitive set of relative references reachable from a document,
  and one rewrites a document's relative references given a path-to-name mapping, without merging anything.
  `CompositionError` is the failure type.
- `nodl_schema/validator.py`: `load_nodl` takes a `base` for the origin of a document loaded from text.
  The CLI gains `--list-references`, reporting a document's transitive relative references for CMake dependency
  tracking, and `--rewrite-to`, emitting a rewritten document. Both are flags on the existing interface rather than
  subcommands, so `python -m nodl_schema <file>` keeps working unchanged.
- `ament_nodl/cmake/ament_nodl_register_node.cmake`: keeps the per-package registration record and its duplicate-name
  check, queries the transitive reference set at configure time and adds it to the custom command's `DEPENDS` and to
  `CMAKE_CONFIGURE_DEPENDS`, rewrites the document, and installs the rewritten copy in place of the source file.
- Resolution is pluggable so the merge and cycle logic are unit-tested with an in-memory fake resolver, with a
  separate end-to-end test resolving a real `nodl://` reference through the installed ament index.
  Relative references need coverage the fake resolver cannot give: a temp-directory test for origin threading, and a
  `test_ament_nodl` case that registers a shared document, registers a second document that relatively includes it, and
  asserts that the installed resource carries the rewritten `nodl://` ref and that a downstream package resolves the
  chain with no knowledge of the source layout.
  The two configure-time errors need coverage in `test_macro_rejection.py`: referencing an unregistered file, and
  registering one name twice from different files.
