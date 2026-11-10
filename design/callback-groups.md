# #232: Declarative C++ callback groups

Status: Implemented for review on the stated base, including both design-review corrections.
Base: upstream `main` at `11cb6caf16cc0103053bbdc8c0698351c08e7bf5`, verified 11 November 2026.
Issue: [#232](https://github.com/ros-tooling/nodl/issues/232), part of [#214](https://github.com/ros-tooling/nodl/issues/214).

# I. Design Contract

## Proposal and scope

Let authors assign generated C++ subscriptions and service servers to named callback groups through `codegen.cpp`.
This permits independent handlers to make progress under a multithreaded executor without handwritten endpoint construction.
Emerson [prefers proposal A](https://github.com/ros-tooling/nodl/issues/232#issuecomment-6453375231) to reduce boilerplate; the detailed contract below remains a recommendation.

Initially support regular nodes and the proposed activation-gated lifecycle bases.
Defer handwritten configuration B, Python, clients, actions, public group access, executor configuration, and lifecycle-transition scheduling.
Core interface validation and conformance must not interpret callback groups.

Required outcomes:

- Absent metadata must preserve existing generated behavior.
- Assigned endpoints must use the declared group; unassigned endpoints must use the ROS default group.
- Invalid or duplicate assignments must fail generation before outputs are written.
- Lifecycle gates must retain their existing behavior independently of group assignment.
- A runtime fixture must prove separate-group concurrency, shared-group serialization, and reentrant overlap.

## Critical boundary and readiness

Callback groups control scheduling; activation gates control admission to application handlers.
Neither provides a guarantee that a lifecycle transition waits for an already-running handler.
Separate groups may permit overlap with lifecycle hooks; authors must synchronize shared application state.

Checked-in generator and runtime fixtures now cover the behavior described below.
Activation-gated integration was also verified in a temporary composition with the open lifecycle dependency; this does not mean that dependency is merged.

The user accepted proposal A, the initial endpoint scope, root-owned exact-name assignments, and the lifecycle-overlap contract.
No #232 implementation branch existed before this design worktree was created.

# II. Engineering Design

## Proposed code tree

Existing owners, with new fixture paths to be selected during implementation:

```text
nodl_generator_cpp/nodl_generator_cpp/
  schemas/codegen_cpp.schema.yaml  Group syntax on role NODE only.
  models.py                       Regenerated typed metadata.
  generate.py                     Retain root configuration; validate owned endpoints.
  template.py                     Explicit group/member context for rendering.
  templates/node.{hpp,cpp}.j2      Retained groups and endpoint options.
nodl_generator_cpp/test/           Schema, ownership, errors, golden output.
test_nodl_generators/              Canonical C++ concurrency and lifecycle fixtures.
nodl_generator_cpp/doc/overview.md Author configuration and concurrency limits.
```

Reuse runtime gate helpers; change their interfaces only if forwarding is insufficient.
No new dependency or core schema field is expected.

## Metadata and validation

Proposed example; endpoint declarations and provider includes are omitted:

```yaml
codegen:
  cpp:
    role: NODE
    callback_groups:
      processing:
        type: MUTUALLY_EXCLUSIVE
        subscriptions: [image]
      control:
        type: MUTUALLY_EXCLUSIVE
        service_servers: [status]
```

The generator schema must accept `MUTUALLY_EXCLUSIVE` and `REENTRANT`.
Group identifiers must match `^[a-z][a-z0-9_]*$`; generated members use a fixed prefix, for example `nodl_callback_group_processing_`.
Each group must contain at least one endpoint assignment.
Unknown fields, unsupported endpoint categories, invalid types, repeated assignments within or across groups, and unknown endpoints must fail.
The error must identify the group, category, and offending name.
The same endpoint name in different categories identifies different entities.

## Includes, names, and ownership

Only the root `NODE` metadata owns the group configuration.
Assignments may reference endpoints from ordinary includes that the generator owns.
Assignments must not target endpoints supplied by `BASE_CLASS` or excluded by `NO_GENERATE`.
Included `NODE` metadata remains invalid; no group inheritance or override policy is introduced.

Match exact declared names within their endpoint category, before namespaces or remappings.
`image`, `/image`, and `~/image` remain distinct; globs and generated C++ member names are not selectors.
Group identifiers are local C++ configuration names, not ROS graph names.

The [current planner](https://github.com/ros-tooling/nodl/blob/11cb6caf16cc0103053bbdc8c0698351c08e7bf5/nodl_generator_cpp/nodl_generator_cpp/generate.py) already separates provider-owned and generated endpoints.
The [common merge](https://github.com/ros-tooling/nodl/blob/11cb6caf16cc0103053bbdc8c0698351c08e7bf5/nodl_schema/nodl_schema/composition.py) does not preserve codegen metadata.
Retain root groups in the planner and validate against the final generated endpoint set; do not change generic composition to recover metadata.
Both `cmake_deps()` and `generate_cpp()` must call the same semantic assignment validator after planning and before producing output.
Tests must prove invalid assignments fail both CLI modes without writing output files.

## Construction and lifecycle integration

```text
root metadata + owned endpoints -> validated assignments
    -> construct ROS node -> create and retain groups -> create endpoints
    -> executor schedules callback -> existing lifecycle gate -> handler
```

Create groups once, before endpoints, and retain them until the endpoints are destroyed.
Use `SubscriptionOptions.callback_group` for subscriptions and the callback-group creation argument for service servers.
When metadata is absent, preserve existing creation calls rather than changing their defaults.
Do not create executor threads or change QoS from this metadata.

Upstream lifecycle evidence as of this design:

| PRs | Verified state | Integration constraint |
| --- | --- | --- |
| [#269](https://github.com/ros-tooling/nodl/pull/269), [#270](https://github.com/ros-tooling/nodl/pull/270) | Open | C++ lifecycle base and gated subscriptions/services; not merged into the stated base. |
| [#271](https://github.com/ros-tooling/nodl/pull/271), [#275](https://github.com/ros-tooling/nodl/pull/275) | Open | Preserve client/action behavior; these categories are outside the first scope. |
| [#281](https://github.com/ros-tooling/nodl/pull/281), [#283](https://github.com/ros-tooling/nodl/pull/283) | Draft | Shared generator paths, parameter locking and refresh; no group assignment for parameter hooks. |

Retain the existing subscription gate wrapper and add endpoint options around it.
The [gated-service helper](https://github.com/ros-tooling/nodl/blob/4041fde765112fcdf6fddb8fa557a52862e7cd95/nodl_runtime_cpp/include/nodl_runtime_cpp/active_only_service.hpp) already forwards QoS and callback-group arguments.
Do not duplicate its admission logic.

The [proposed lifecycle base](https://github.com/ros-tooling/nodl/blob/4041fde765112fcdf6fddb8fa557a52862e7cd95/nodl_runtime_cpp/include/nodl_runtime_cpp/lifecycle_node.hpp) opens the gate before `handle_activate` and closes it after a successful `handle_deactivate`.
Admission is checked when the wrapper executes, not a promise about middleware arrival time.
Closing the gate does not interrupt a handler already admitted.
Keep groups across transitions; do not recreate endpoints or groups on activation.
Lifecycle and parameter infrastructure keep their existing group assignment.
An application status service remains gated even if assigned to another group.
Parameter locking does not make other application state thread-safe.

## Test and delivery contract

| Requirement | Evidence to deliver |
| --- | --- |
| Syntax and failure rules | Schema/model tests for both types, malformed IDs, empty groups, unknown fields/categories, and duplicate assignments. |
| Ownership and exact names | Include-tree tests for owned/provider endpoints, root-only metadata, category distinctions, and relative/absolute/private names. |
| Construction and defaults | Golden output plus compilation; group initialization before endpoints, retained references, both QoS/group arguments forwarded, unchanged no-metadata output. |
| Scheduling | Coordinated runtime barriers: separate groups permit a status response during blocked work; a shared group serializes; reentrant callbacks overlap. |
| Lifecycle | Assigned handlers are gated when inactive, deliver when active, and retain assignments after repeated transitions; explicitly exercise possible hook/handler overlap. |
| Compatibility | Supported-distribution builds and existing generator tests; tested documentation uses the checked-in fixture. |

Register concurrency executables explicitly with ament/CTest under `BUILD_TESTING`; `add_cpp_fixture()` alone only builds them.
Use bounded waits, release blocked callbacks on failure, isolate ROS communication between parallel tests, and prove registration with `colcon test` results.

Phase 1: schema, planner, generation, ordinary-node fixture, and author documentation.
Gate: validation/golden tests and compiled runtime concurrency checks pass.
Phase 2: compose with the settled #269/#270 interfaces and add lifecycle fixture coverage.
Gate: lifecycle admission and transition/concurrency tests pass without changing gating policy.
Check compatibility with the latest parameter-stack templates before final review; do not require those drafts to merge solely for this feature.

Keep edits to shared generator templates serialized with lifecycle work.
Record the exact dependency SHAs when implementation starts; do not silently stack on every lifecycle draft.
Stop for review if integration requires changed gate semantics, provider ownership, a public C++ customization API, or broader endpoint scope.

Alternative B remains viable and more flexible for sharing groups with handwritten endpoints, but adds constructor API and configuration boilerplate.
Supporting both now would add precedence and testing combinations without a demonstrated requirement.

Existing documents need no migration.
Removing group metadata restores default scheduling; it may reduce concurrency, so application behavior must be rechecked.

## Final audit

The implementation adds root-only metadata, generated models, one assignment validator shared by both entry points, template wiring, and author documentation.
The new golden case and `test_callback_groups.py` cover generation and failure behavior.
The canonical fixtures live in `test_nodl_generators/callback_groups/cpp`; `ament_add_gtest(test_cpp_callback_groups ...)` registers their execution with CTest.
Fixture libraries use `STATIC NO_INDEX` and do not change installed resources or exported APIs.

Verification:

- Jazzy: `colcon test` for `nodl_schema`, `nodl_generator_common`, `nodl_generator_cpp`, `nodl_generator_py`, and `test_nodl_generators` reported 843 checks, no errors or failures, and four skips.
  The skips are two optional pyright tests, one environment-dependent setuptools develop test, and the gate-specific case unavailable with main's ungated lifecycle provider.
- Humble: compiled the actual generated outputs and ran the same registered C++ runtime fixture successfully; its gate-specific case is likewise unavailable.
- Gated lifecycle: a temporary source composition with #270 at `57510a9cd1cf3b84003dd5771b2360311ed80a6c` passed all six runtime cases with no skips.
  Composition required resolving overlapping generator edits and forwarding group options through the existing wrappers; none of that upstream implementation was copied into this main-based diff.
- Repository pre-commit checks and the combined Sphinx build with warnings as errors passed.

No accepted metadata or ownership semantics were changed.
Lyrical/Rolling remain CI verification, and final gated integration requires reconciliation with whichever lifecycle revisions merge.
The draft PR must state those limits and must not claim the lifecycle stack has merged or close #232 on partial integration evidence.
