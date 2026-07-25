# Ament NoDL CMake Macros

## Summary

Three CMake macros for installing and registering NoDL interface files.

## Macros

### `ament_nodl_install`

Base layer. Validates and installs NoDL files.

```cmake
ament_nodl_install(
  FILES
    nodl/foo.nodl.yaml
    nodl/bar.nodl.yaml
)
```

What it does:

1. Validates each file at build time (`python -m nodl_schema`)
2. Installs to `share/<pkg>/nodl/`
3. Registers under the `nodl_interfaces` ament index resource type (for
   enumeration by tooling)

Idempotent — safe to call multiple times for the same file (e.g. when a
higher-level macro also calls it internally).

Standalone use cases: fragment packages that export reusable interfaces,
documentation-only specs.

### `ament_nodl_register_executable`

For standalone node executables. Maps an executable name to a NoDL spec.

```cmake
ament_nodl_register_executable(foo_node
  FILE nodl/foo.nodl.yaml
)
```

What it does:

1. Calls `ament_nodl_install` for the file
2. Registers a `nodl_executables` ament index resource mapping the executable
   name to the installed NoDL file

Resource content (one line per executable, appended):

```
# share/ament_index/resource_index/nodl_executables/<pkg>
foo_node:nodl/foo.nodl.yaml
```

### `ament_nodl_register_component`

For composable nodes. Maps a component class to a NoDL spec.

```cmake
ament_nodl_register_component(my_pkg::FooNode
  FILE nodl/foo.nodl.yaml
)
```

What it does:

1. Calls `ament_nodl_install` for the file
2. Registers a `nodl_components` ament index resource mapping the
   fully-qualified component class name to the installed NoDL file

Resource content:

```
# share/ament_index/resource_index/nodl_components/<pkg>
my_pkg::FooNode:nodl/foo.nodl.yaml
```

## Ament Index Resource Types

| Resource type | Key | Content | Purpose |
|---|---|---|---|
| `nodl_interfaces` | `<pkg>` | List of installed NoDL filenames | Enumerate available interfaces |
| `nodl_executables` | `<pkg>` | `<exe>:<nodl_file>` lines | Map live executables → specs |
| `nodl_components` | `<pkg>` | `<class>:<nodl_file>` lines | Map component classes → specs |

## Automatic Registration

Higher-level tools are expected to call these macros internally:

- **Node codegen** calls `ament_nodl_register_executable` or
  `ament_nodl_register_component` automatically when generating a node from a
  NoDL spec.
- **Codegen "provides implementation" macros** (e.g. a future macro that
  declares a package provides an implementation for an included interface) call
  `ament_nodl_install` automatically for any NoDL files they reference.

Users only call the macros directly when hand-writing nodes or exporting
standalone interface fragments.
