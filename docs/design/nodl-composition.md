# NoDL Composition & Code Generation

## Summary

Extend NoDL with a single new schema field — `includes` — to support interface
composition. Keep all code-generation and implementation concerns out of the
schema entirely.

## Principles

1. **A NoDL document describes an interface, nothing else.**
   Topics, services, actions, parameters. No implementation metadata.

2. **Everything is a fragment.**
   There is no `kind` or `type` discriminator. A "mixin" is just a doc that
   gets included. A "node base" is just a doc whose interface happens to
   describe a lifecycle node. The schema treats them all the same.

3. **Composition is interface union.**
   `includes` merges the interface of other NoDL documents into the current
   one. The result is the union of all declared topics, services, actions,
   and parameters.

4. **Implementation binding is a codegen concern.**
   How an included interface maps to code (base class, member component,
   generated boilerplate) is owned by the codegen backend, not the schema.

## Schema Change

One new optional top-level field:

```yaml
nodl_version: 2

includes:
  - ref: nodl://rclcpp_lifecycle/lifecycle_node
  - ref: nodl://tf2_ros/tf_listener
  - ref: nodl://my_package/common_diagnostics

publishers:
  - name: /cmd_vel
    type: geometry_msgs/msg/Twist
    qos: {history: KEEP_LAST, depth: 1, reliability: RELIABLE}
```

`includes` is a list of objects, each with a `ref` key:

| Form | Example | Resolution |
|---|---|---|
| Package URI | `nodl://tf2_ros/tf_listener` | `<prefix>/share/tf2_ros/nodl/tf_listener.nodl.yaml` |

Packages can self-reference their own installed schemas
(e.g. `nodl://my_package/common_diagnostics`).

## Include Resolution

Package URIs are resolved using the existing ament package index:

1. Parse `nodl://tf2_ros/tf_listener` → package=`tf2_ros`, name=`tf_listener`
2. `prefix = get_package_prefix('tf2_ros')`
3. `path = <prefix>/share/tf2_ros/nodl/tf_listener.nodl.yaml`

No new ament index resource type is required for resolution. The `packages`
marker that every package already installs is sufficient.

## API Layering

Two distinct operations, two distinct functions:

| Function | Purpose | Follows paths? | Used by |
|---|---|---|---|
| `validate(data)` | JSON schema check on a single file's dict | No | CMake macro (`python -m nodl_schema`), `ros2 nodl validate` |
| `load_nodl(source, source_path=...)` | Parse + validate + recursively resolve includes → merged `NodlDocument` | Yes | Codegen, tooling, anything that needs the full interface |

`validate()` stays a pure syntax/structure check — it confirms `includes`
entries are well-formed objects with `ref` keys, but never opens another file.
This is what build-time validation needs: "is this file valid NoDL?" without
requiring the dependency graph to be installed.

`load_nodl()` is the "give me the real thing" entry point — validate, follow
refs, deduplicate diamonds, merge interfaces, return a single resolved
`NodlDocument`.

## Current Consumers

All schema consumers already go through `nodl_schema`:

| Consumer | Entry point |
|---|---|
| `ros2 nodl validate` verb | `load_nodl(source)` (result discarded — only checks for errors) |
| `python -m nodl_schema` CLI | `load_nodl(f)` (same — validate-only) |
| `ament_nodl_install` CMake macro | Shells out to `python -m nodl_schema <file>` |
| `ament_nodl_register_executable` CMake macro | Calls `ament_nodl_install` internally |
| `ament_nodl_register_component` CMake macro | Calls `ament_nodl_install` internally |
| `nodl/doc/schema_reference.py` | Reads raw YAML for doc rendering — no `NodlDocument` parsing |
| `ros2 nodl describe` verb | Runtime observation via C++ binary — no `.nodl.yaml` files touched |

No caller currently consumes the `NodlDocument` for downstream logic. The
centralised entry point means adding resolution is a **single-package change
in `nodl_schema`**.

## Ament Index Registration (Discovery)

Three ament index resource types are registered at install time. None are used
for include resolution.

### `nodl_interfaces`

Registered by `ament_nodl_install`. Lists the NoDL filenames (bare names, no
path prefix) installed by a package. Used for enumeration/tooling
(e.g. `ros2 nodl list`).

```
share/ament_index/resource_index/nodl_interfaces/tf2_ros
# content: tf_listener.nodl.yaml\ntf_buffer.nodl.yaml
```

### `nodl_executables`

Registered by `ament_nodl_register_executable`. Maps an executable name to its
installed NoDL file path (relative to the package share directory).

```
share/ament_index/resource_index/nodl_executables/tf2_ros
# content: tf_listener_node:nodl/tf_listener.nodl.yaml
```

### `nodl_components`

Registered by `ament_nodl_register_component`. Maps a fully-qualified component
class name to its installed NoDL file path.

```
share/ament_index/resource_index/nodl_components/tf2_ros
# content: tf2_ros::TfListener:nodl/tf_listener.nodl.yaml
```

## Codegen Sidecars

Implementation metadata lives in codegen-owned sidecar files, co-located with
the NoDL doc by convention:

```
share/tf2_ros/nodl/
    tf_listener.nodl.yaml      # interface (owned by NoDL)
    tf_listener.cpp.yaml       # C++ binding (owned by cpp codegen backend)
```

The sidecar format is defined by each codegen backend. The NoDL schema does not
reference or constrain it. A backend resolves an include, finds the
`.nodl.yaml`, then checks for a sibling sidecar. If present, the included
interface has an implementation the backend can use. If absent, the backend
generates everything from the interface alone.

Sidecar files are registered under their own ament index resource type
(e.g. `nodl_cpp_bindings`) for discovery, following the same pattern.

## Resolved Questions

### Conflict semantics

When two included fragments declare the same topic name, parameter name, or
other interface element, the resolver applies **merge-if-identical** semantics:

- If both declarations are structurally equal (same type, QoS, default value,
  validators, etc.), the duplicate is silently deduplicated.
- If they differ in any field, resolution fails with an error that names the
  conflicting element and the two source files.

This is the right balance: pure-error is too strict (diamond includes that
share a common base would always fail), and explicit overrides add schema
complexity that is not yet justified. The including document can still
"override" by declaring the same element locally — the local declaration wins
over any included one, and a conflict among includes is still an error.

If override semantics are needed in the future, the object form of `includes`
leaves room to add an `overrides` key without a breaking change.

### Parameter namespacing

Mixin authors are responsible for namespacing their own parameters. The schema
does **not** provide a `parameter_prefix` mechanism on includes.

Rationale:
- A prefix that only applies to parameters but not to topics, services, or
  actions creates an inconsistency in the model.
- Dot-separated parameter namespacing (e.g. `tf.timeout`) is already an
  established ROS 2 convention; fragments should use it.
- The object form of `includes` leaves room to add a prefix key later if
  real-world usage proves it necessary.

### Include entry shape

Includes entries are **objects** with a `ref` key:

```yaml
includes:
  - ref: nodl://tf2_ros/tf_listener
```

Bare strings would be marginally simpler to write but would require a breaking
schema change if any per-include option (overrides, prefix, feature flags) is
ever needed. Objects cost almost nothing today and keep the door open.

### Completeness validation

Completeness is a **codegen-backend concern**, not a schema concern. The NoDL
schema validates structure: "is this a well-formed interface description?" It
does not know or care whether the result is sufficient for a particular code
generator.

Each codegen backend defines its own completeness rules. For example, a C++
backend might require exactly one included fragment that provides a node base
class. Those rules are checked by the backend at generation time, not by
`validate()` or `load_nodl()`.

### Diamond includes

Diamond includes are resolved by **canonical-path deduplication**. During
recursive resolution, `load_nodl()` tracks the set of already-resolved
canonical file paths. When an include resolves to a path already in the set,
it is skipped. This guarantees that each unique fragment contributes its
interface exactly once to the merged result, regardless of how many times it
appears in the include graph.

The resolution order is depth-first, left-to-right (i.e. the order entries
appear in the `includes` list). The first occurrence wins for deduplication
purposes, though with merge-if-identical semantics the order only matters for
diagnostic messages.

### Sidecar naming convention

The recommended convention is **`<name>.<backend>.yaml`**
(e.g. `tf_listener.cpp.yaml`). Each codegen backend owns its sidecar format
and may deviate, but this default is recommended to reduce cross-project
fragmentation.

Alternatives considered and rejected:
- `<name>.codegen.yaml` with a `backend` key inside — forces all backends
  into a single file, making per-backend installation awkward.
- A per-package manifest listing all bindings — adds a layer of indirection
  with no clear benefit over filesystem co-location.
