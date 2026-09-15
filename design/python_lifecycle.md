# Python lifecycle-node generation from NoDL

Status: Implemented; full supported-distribution verification pending CI

# I. Design Contract

## 1. Objective and context

The Python generator must generate an `rclpy.lifecycle.LifecycleNode` base class when a NoDL document includes the standard Python lifecycle-node provider.

This is a bounded parity change with the C++ generator, not a direct template copy.
The shared provenance pipeline and the C++ base-provider pattern already solve include resolution, base selection, and entity filtering.
Python also requires an explicit lifecycle-publisher factory because `rclpy.lifecycle.LifecycleNode` provides `create_lifecycle_publisher()` separately from `Node.create_publisher()`.

Users will select lifecycle behavior by including:

```yaml
include:
  - ref: nodl://rclpy/lifecycle_node
```

Existing flat Python NoDL documents must continue to generate subclasses of `rclpy.node.Node` with byte-equivalent output.

## 2. Scope

### In scope

- Resolve transitive includes for CLI and CMake-driven Python generation.
- Read and validate `codegen.python` base-provider metadata.
- Select either `rclpy.node.Node` or one included Python base class.
- Filter entities already supplied by an included base provider.
- Generate managed lifecycle publishers with `create_lifecycle_publisher()`.
- Track transitive NoDL inputs so CMake rebuilds generated Python when an include changes.
- Add standard `nodl://rclpy/node` and `nodl://rclpy/lifecycle_node` providers without copying the node-interface entity lists.
- Test generated lifecycle inheritance, lifecycle transitions, and publisher activation.
- Document lifecycle subclass responsibilities.

### Non-goals

- Do not generate lifecycle transition callbacks such as `on_configure()` or `on_activate()`.
- Do not move entity or parameter creation from the generated constructor into lifecycle callbacks.
- Do not make subscriptions, services, clients, or actions lifecycle-managed.
- Do not add Python node mixins.
- Do not change C++ generation or its public include URIs.
- Do not require existing flat Python documents to include `nodl://rclpy/node`.

## 3. Required outcomes

R1. The Python CLI must resolve the complete include tree before it renders code.

R2. A document with one included `codegen.python` `BASE_CLASS` provider must inherit from the provider's configured class.

R3. A document without a Python base provider must retain the current implicit `rclpy.node.Node` base.

R4. A document with more than one visible Python base provider must fail with an error that names the conflicting classes.

R5. The lifecycle provider must generate an import of `rclpy.lifecycle.LifecycleNode`, inheritance from `LifecycleNode`, and publisher creation through `create_lifecycle_publisher()`.

R6. The generator must not recreate publishers, services, or parameters that the selected base provider already supplies.

R7. The default lifecycle callbacks supplied by `rclpy` must remain intact.
Application subclasses may override them and must call the corresponding `super()` callback when they want generated lifecycle publishers to follow activation and deactivation transitions.

R8. The CMake macro must depend on the root NoDL file and all transitive includes.

R9. Existing flat-document generated modules and end-to-end behavior must not change.

## 4. System overview

```text
root .nodl.yaml
       |
       v
NoDL include resolver
       |
       v
shared provenance walk ----> Python BASE_CLASS metadata
       |                              |
       |                              v
       +--------------------> base class + publisher method
       |
       v
entities not supplied by the base
       |
       v
Python renderer -----------> generated module and optional parameters module
       |
       v
transitive source list ----> CMake configure/build dependencies
```

The NoDL schema continues to treat `codegen` as tool-owned opaque metadata.
The Python generator owns validation and interpretation of `codegen.python`.

## 5. Acceptance tests and readiness

- A generated lifecycle class is an `rclpy.lifecycle.LifecycleNode` at runtime.
- Its declared publisher is an `rclpy.lifecycle.LifecyclePublisher`.
- The publisher does not deliver before activation, delivers while active, and stops delivering after deactivation.
- Lifecycle services and base-node entities occur once and are not scaffolded as generated callbacks or members.
- An included NoDL file change rebuilds the generated module through `nodl_generate_py()`.
- Existing Python generator unit and end-to-end fixtures remain green on Humble, Jazzy, Kilted, Lyrical, and Rolling.

There is no known design blocker.
Implementation must verify the lifecycle API on every supported ROS distribution before merge.

# II. Engineering Design

## 6. Proposed code tree

The tree is provisional where a test helper may fit an existing module better during implementation.

```text
nodl_generator_py/
|-- nodl_generator_py/
|   |-- schemas/codegen_python.schema.yaml
|   |   Validate Python-owned base-provider metadata.
|   |-- models.py
|   |   Represent the validated Python base-provider contract.
|   |-- schema.py
|   |   Load and validate codegen.python.
|   |-- provenance.py
|   |   Adapt codegen.python to the shared provenance walk.
|   |-- generator.py
|   |   Resolve files, select a base, filter entities, and render output.
|   |-- cli.py
|   |   Generate from a source path and emit CMake dependency data.
|   `-- templates/node.py.jinja2
|       Render the configured base class and publisher method.
|-- cmake/nodl_generate_py.cmake
|   Track the complete include tree and generator inputs.
|-- test/
|   |-- _includes/
|   |   Provide registered-reference substitutes for unit tests.
|   |-- fixtures/lifecycle_node.nodl.yaml
|   |   Exercise lifecycle base selection and entity filtering.
|   `-- test_*.py
|       Cover metadata, provenance, rendering, errors, and CLI dependencies.
`-- doc/overview.md
    Document includes, lifecycle behavior, and subclass responsibilities.

nodl_common_interfaces/
|-- nodl/rclpy_node.nodl.yaml
|   Provide Python Node metadata over the existing node entity contract.
|-- nodl/rclpy_lifecycle_node.nodl.yaml
|   Provide Python LifecycleNode metadata over the existing lifecycle contract.
|-- CMakeLists.txt
|   Register both documents under the rclpy resource namespace.
`-- doc/overview.md
    List the new provider URIs and generated base classes.

test_nodl_generators/
|-- lifecycle/nodl/node.nodl.yaml
|   Canonical end-to-end lifecycle input.
|-- lifecycle/python/node_impl.py
|   Minimal handwritten subclass.
|-- lifecycle/python/test_node.py
|   Verify state transitions and managed publisher behavior.
|-- CMakeLists.txt
|   Generate and register the lifecycle fixture test.
`-- package.xml
    Declare lifecycle test dependencies.
```

## 7. Evidence and decisions

### Confirmed repository facts

- The current Python generator rejects every `include` entry and always imports `rclpy.node.Node` ([`nodl_generator_py/nodl_generator_py/generator.py`](../nodl_generator_py/nodl_generator_py/generator.py), lines 130-138).
- The current template always inherits from `Node` and calls `self.create_publisher()` ([`nodl_generator_py/nodl_generator_py/templates/node.py.jinja2`](../nodl_generator_py/nodl_generator_py/templates/node.py.jinja2), lines 10-24).
- The shared generator package already returns barriers, filtered entities, and transitive source paths from one file-based operation ([`nodl_generator_common/nodl_generator_common/provenance.py`](../nodl_generator_common/nodl_generator_common/provenance.py), lines 152-180).
- The C++ generator already validates one base provider and consumes the shared result ([`nodl_generator_cpp/nodl_generator_cpp/generate.py`](../nodl_generator_cpp/nodl_generator_cpp/generate.py), lines 40-64 and 112-134).
- The NoDL schema intentionally leaves language metadata to each generator ([`nodl_schema/nodl_schema/schemas/nodl.schema.yaml`](../nodl_schema/nodl_schema/schemas/nodl.schema.yaml), lines 31-38).
- The current Python CMake rule depends only on the root NoDL file, so it cannot correctly rebuild for transitive includes ([`nodl_generator_py/cmake/nodl_generate_py.cmake`](../nodl_generator_py/cmake/nodl_generate_py.cmake), lines 39-56).
- The repository already has runtime tests for generated Python nodes in `test_nodl_generators` ([`test_nodl_generators/CMakeLists.txt`](../test_nodl_generators/CMakeLists.txt), lines 9-27).
- The supported ROS matrix is Humble through Rolling ([`README.md`](../README.md), lines 51-54; [`.github/workflows/test.yml`](../.github/workflows/test.yml), line 47).
- Upstream `rclpy` defines `LifecycleNode`, default transition callbacks, and `create_lifecycle_publisher()` as separate lifecycle APIs ([`rclpy.lifecycle.node`](https://github.com/ros2/rclpy/blob/rolling/rclpy/rclpy/lifecycle/node.py)).

### Decisions

D1. Reuse `nodl_generator_common.resolve_provenance()` instead of adding Python-specific include traversal.

D2. Keep the existing implicit `Node` default for backward compatibility.
Python base metadata is optional, but at most one provider may be visible.

D3. Add thin `rclpy` provider documents that include the existing common-interface documents.
The outer Python barrier owns the complete subtree, so the node and lifecycle entity lists remain single-source.

D4. Put the publisher creation method in provider metadata.
Do not infer lifecycle behavior from a class-name string in the renderer.

D5. Create generated publishers in `__init__`, as the current Python and C++ generators do.
The lifecycle publisher itself controls whether publication is enabled.

D6. Keep lifecycle transition policy in `rclpy` and handwritten subclasses.
The generator must not emit overrides that could bypass or duplicate upstream behavior.

D7. Copy the C++ configure-time dependency-file pattern in reduced form.
Python needs the resolved source list but does not need C++ link dependencies.

### Assumptions and external dependencies

- `LifecycleNode` accepts the same generated `super().__init__(node_name, **kwargs)` call shape on every supported distribution.
- `create_lifecycle_publisher()` and default lifecycle callbacks manage publisher activation on every supported distribution.
- Phase 1 must replace these assumptions with tests against the repository's ROS distribution matrix.

## 8. Architecture and lifecycle

### Metadata contract

The Python generator will own this proposed `codegen.python` shape:

```yaml
codegen:
  python:
    role: BASE_CLASS
    module: rclpy.lifecycle
    class: LifecycleNode
    publisher_method: create_lifecycle_publisher
```

`role` must be `BASE_CLASS`.
`module` must be a dotted Python module name.
`class` and `publisher_method` must be Python identifiers.
`publisher_method` defaults to `create_publisher` when omitted.
Unknown fields must fail validation.

The standard node provider uses `module: rclpy.node`, `class: Node`, and the default publisher method.
The standard lifecycle provider uses the metadata shown above.

### Generation flow

The CLI passes the root `Path` to a file-based generator entry point.
That entry point resolves provenance with the Python metadata adapter.
It selects the implicit Node configuration or the single included provider.
It passes only filtered entities, the selected import, class name, and publisher method to the pure renderer.

The existing in-memory `generate_python(NodlDocument, target_name)` and `generate_parameter_yaml()` exports must remain available for flat documents.
They retain implicit Node behavior and avoid a compatibility break for library callers.
The new file-based entry point owns include resolution because a detached `NodlDocument` has no origin for relative references.

### Runtime lifecycle

The generated constructor creates publishers with `create_lifecycle_publisher()`.
`rclpy` registers each lifecycle publisher as a managed entity.
The default transition callbacks configure, activate, deactivate, clean up, and shut down managed entities.

A handwritten subclass may override transition callbacks.
If it wants the default managed-entity transition, it must return the corresponding `super()` result or otherwise invoke equivalent upstream behavior.
The generated class must not force an application transition policy.

Parameters, subscriptions, services, clients, and actions keep their current constructor-time behavior.
This proposal does not claim that these entities become inactive with the node.

## 9. Interfaces, errors, and compatibility

The existing CLI invocation remains unchanged:

```text
python -m nodl_generator_py --nodl-file F --output-dir D --target-name T
```

A configure-time dependency mode will write `<target>_deps.cmake` with `<target>_NODL_SOURCES`.
Its naming and formatting should follow `nodl_generator_cpp --cmake-deps` where applicable.

Generation must fail before writing output when:

- `codegen.python` does not match its schema;
- more than one Python `BASE_CLASS` provider is visible;
- include resolution fails;
- the selected import, class, or publisher method is invalid.

Errors must identify the source file and the conflicting or invalid value.
The CLI keeps its current nonzero return and stderr diagnostic behavior.

Flat documents remain compatible.
Documents that previously failed only because they used `include` may now succeed, so there is no migration requirement.
The generated output changes only when Python provider metadata changes the selected base or publisher method, or when included entities contribute to the merged document.

## 10. Alternatives and trade-offs

### Copy the C++ implementation literally

This reuses the most code shape, but it would still call `create_publisher()` and produce a normal Python publisher.
It would therefore provide lifecycle inheritance without managed publisher behavior.
Reject this alternative.

### Detect `LifecycleNode` by class name

This avoids one metadata field, but it couples the renderer to one upstream class spelling and prevents compatible custom bases.
Reject this alternative in favor of explicit `publisher_method` metadata.

### Duplicate all node entities in new rclpy documents

This makes each provider document self-contained, but it creates two copies of the standard node and lifecycle interface contract.
Reject this alternative.
Thin Python provider documents will include the existing entity documents and place the Python barrier above them.

### Require a base provider for all Python documents

This matches the current C++ rule, but it breaks every existing flat Python document.
Reject this alternative for this change.
The implicit Node base may be deprecated separately if a future design justifies the migration.

### Generate lifecycle callbacks

This can make subclass behavior more explicit, but it introduces policy that is absent from the NoDL input and risks overriding `rclpy` managed-entity behavior.
Reject this alternative.

## 11. Operational qualities

The feature adds no persistence, network trust boundary, secret handling, or user-controlled dynamic import at runtime.
The generator validates metadata before it writes import statements.
Generated code imports only the statically configured provider module and declared ROS interface packages.

CMake must treat all transitive NoDL sources as configure and build dependencies.
A failed reconfigure or generation leaves the previous generated file possible on disk, but the build target must fail and must not report success.
Rollback consists of reverting the generator, provider registrations, fixture, and documentation in the same change set.

## 12. Detailed test contract

| Requirement | Test location | Canonical evidence |
|---|---|---|
| R1, R6 | `nodl_generator_py/test/test_provenance.py` | A lifecycle provider includes the node provider; all provider-owned entities are filtered and root entities remain. |
| R2, R5 | Python golden or AST test | The module imports and inherits `LifecycleNode`; declared publishers call `create_lifecycle_publisher()`. |
| R3, R9 | Existing `test_generator.py` plus golden comparison | Existing flat fixture output is unchanged. |
| R4 | `nodl_generator_py/test/test_error.py` | Two sibling Python base providers fail and both class names occur in the diagnostic. |
| Metadata validation | `nodl_generator_py/test/test_schema.py` | Missing required fields, invalid identifiers, and unknown fields fail; valid Node and LifecycleNode configurations load. |
| R6 | CLI fixture | Generated output contains no callbacks or members for lifecycle services, `/rosout`, `/parameter_events`, or `use_sim_time`. |
| R7 | `test_nodl_generators/lifecycle/python/test_node.py` | A subclass with no transition overrides uses upstream defaults; a documented override fixture calls `super()`. |
| Lifecycle runtime | Same end-to-end test | Type is `LifecyclePublisher`; delivery is disabled before activation, enabled while active, and disabled after deactivation. |
| R8 | CLI dependency test and CMake fixture | The deps file contains root and transitive source paths; touching an include makes the generated target stale. |
| Distribution compatibility | CI matrix | All unit and end-to-end tests pass on Humble, Jazzy, Kilted, Lyrical, and Rolling. |

Runtime tests must use bounded executor waits and must destroy nodes and shut down the ROS context in `finally` blocks, consistent with existing end-to-end fixtures.

## 13. Dependency gates and implementation phases

### Phase 1: API and metadata gate

Add the Python metadata schema, model, loader, and focused tests.
Confirm `LifecycleNode`, constructor keywords, `create_lifecycle_publisher()`, and managed transition behavior on the supported CI matrix.

Gate: valid provider metadata loads, invalid metadata fails, and a minimal hand-written lifecycle probe passes on all supported distributions.

Rollback: remove the new isolated modules and tests.

### Phase 2: provenance and rendering

Add the Python provenance adapter and file-based generation path.
Parameterize the template base import, base class, and publisher method.
Preserve the flat in-memory API.
Add lifecycle, filtering, conflict, and regression tests.

Gate: R1-R7 and R9 pass in unit tests, and existing flat generated output is unchanged.

Rollback: retain the metadata modules unused or revert the phase.

### Phase 3: providers and build integration

Register thin `rclpy` node and lifecycle providers.
Add configure-time dependency output to the CLI and consume it from `nodl_generate_py()`.
Add registration and transitive-rebuild tests.

Gate: both `nodl://rclpy/...` references resolve from an installed workspace and R8 passes.

Rollback: unregister the providers and restore the root-only CMake dependency path.

### Phase 4: runtime proof and documentation

Add the lifecycle end-to-end fixture and update generator and common-interface documentation.
Document constructor-time entity creation and the `super()` callback rule.

Gate: lifecycle publication follows inactive/active/inactive transitions across the CI matrix, and user-facing docs no longer list lifecycle nodes or include composition as unsupported.

Rollback: remove the fixture and docs together with the feature if a distribution gate fails.

## 14. Parallelism and stop conditions

Metadata/schema work and the runtime probe may proceed in parallel.
Provider registration depends on the accepted metadata contract.
Template integration depends on the provenance result shape.
The final lifecycle runtime test depends on all earlier phases.

Stop and return to design review if any supported ROS distribution lacks `create_lifecycle_publisher()` or has materially different transition semantics.
Stop if lifecycle correctness would require generated transition callbacks or moving entity creation into `on_configure()`.
Stop if the provider design requires duplicated node-interface entity lists.
Do not add include traversal, entity filtering, or codegen-metadata validation to the Jinja template or CMake layer.

## 15. Definition of done

- All required outcomes have implementation and test evidence.
- The Python generator supports transitive includes through the shared provenance core.
- Standard Node and LifecycleNode provider references resolve after installation.
- Lifecycle publishers follow runtime transitions on every supported ROS distribution.
- Existing flat generation remains compatible.
- CMake rebuilds for all transitive inputs.
- Package manifests and installed template/schema assets are complete.
- Documentation explains selection, generated members, lifecycle limits, and subclass callback responsibilities.

## 16. Final audit

Before merge, compare R1-R9 with the actual diff and test results.
Inspect generated lifecycle code and the installed provider documents.
Run the full repository verification required by CI on the supported distribution matrix.
Record any semantically equivalent implementation choices and residual cross-distribution risk.
Do not mark the change complete while the documentation still states that lifecycle nodes or include composition are unsupported.
