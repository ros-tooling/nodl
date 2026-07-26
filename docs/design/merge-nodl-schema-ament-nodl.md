# Merging `nodl_schema` and `ament_nodl`

## Summary

Merge the `ament_nodl` CMake-macro package into `nodl_schema`, producing a
single `ament_cmake_python` package that ships both the Python validation
library and the CMake macros for installing NoDL files. This eliminates a
circular dependency and reflects the reality that these two packages are
tightly coupled halves of the same thing.

## Problem

Adding `includes` resolution to the schema (see `nodl-composition.md`)
creates a circular dependency:

```
ament_nodl ──exec_depend──▶ nodl_schema
    ▲                            │
    └───────test_depend──────────┘
```

- `ament_nodl` depends on `nodl_schema` at runtime because its CMake macros
  shell out to `python -m nodl_schema <file>` for build-time validation.
- `nodl_schema` depends on `ament_nodl` at test time because integration
  tests need to build a test workspace that calls `ament_nodl_install()` to
  verify that NoDL files installed via the macros are discoverable by the
  include resolver.

`colcon` can technically handle a `test_depend` cycle (build both packages
without tests, then run tests), but it is fragile, confusing, and a sign
that the package boundary is in the wrong place.

## Observation

`ament_nodl` contains **no Python code and no logic of its own**. It is four
CMake files and a config template:

```
cmake/ament_nodl_install.cmake
cmake/ament_nodl_package_hook.cmake
cmake/ament_nodl_register_executable.cmake
cmake/ament_nodl_register_component.cmake
ament_nodl-extras.cmake.in
```

Every macro's validation step calls `python -m nodl_schema`. The package's
sole `exec_depend` is `nodl_schema`. It exists only to provide a
`find_package(ament_nodl)` entry point for downstream CMake consumers.

These are not two packages with an unfortunate coupling — they are one package
that was split prematurely.

## Decision

Merge `ament_nodl` into `nodl_schema`. The resulting package:

- Keeps the name **`nodl_schema`** — it is the primary identity (schema,
  models, validator, Python API). The CMake macros are a feature it provides,
  not its reason for existing.
- Uses the **`ament_cmake_python`** build type so it can install both
  a Python package (`nodl_schema`) and CMake macros.
- Keeps the **`ament_nodl_*()`** macro names unchanged. These are the
  user-facing CMake API and there is no reason to rename them. The macro
  names do not need to match the package name.
- Ships the **`nodl_schema-extras.cmake.in`** config template (renamed from
  `ament_nodl-extras.cmake.in`) so that `find_package(nodl_schema)` brings
  the macros into scope.

## Resulting Structure

```
nodl_schema/
├── CMakeLists.txt                      # ament_cmake_python
├── package.xml
├── nodl_schema-extras.cmake.in
├── cmake/
│   ├── ament_nodl_install.cmake
│   ├── ament_nodl_package_hook.cmake
│   ├── ament_nodl_register_executable.cmake
│   └── ament_nodl_register_component.cmake
├── nodl_schema/                        # Python package
│   ├── __init__.py
│   ├── __main__.py
│   ├── models.py
│   ├── validator.py
│   └── schemas/
│       ├── nodl.schema.yaml
│       └── parameter.schema.yaml
├── resource/
│   └── nodl_schema
└── test/
    ├── conftest.py                     # merged from both packages
    ├── test_schema.py                  # unit tests (from nodl_schema)
    ├── test_validator_cli.py           # unit tests (from nodl_schema)
    ├── test_ament_nodl_install.py      # macro tests (from ament_nodl)
    ├── test_register_executable.py     # macro tests (from ament_nodl)
    ├── test_register_component.py      # macro tests (from ament_nodl)
    ├── test_macro_rejection.py         # macro tests (from ament_nodl)
    ├── test_integration.py             # include resolution (from nodl_schema)
    └── test_ws/
        └── src/
            ├── test_ament_nodl/        # from ament_nodl/test/test_ws
            ├── nodl_fragment_a/        # from nodl_schema/test/test_ws
            └── nodl_fragment_b/        # from nodl_schema/test/test_ws
```

## Downstream Changes

| What | Before | After |
|---|---|---|
| `find_package()` in CMake | `find_package(ament_nodl REQUIRED)` | `find_package(nodl_schema REQUIRED)` |
| `package.xml` buildtool dep | `<buildtool_depend>ament_nodl</buildtool_depend>` | `<buildtool_depend>nodl_schema</buildtool_depend>` |
| Macro calls in CMake | `ament_nodl_install(...)` | `ament_nodl_install(...)` (unchanged) |
| `import nodl_schema` in Python | unchanged | unchanged |
| `python -m nodl_schema` CLI | unchanged | unchanged |
| `nodl` metapackage | `exec_depend` on both `ament_nodl` and `nodl_schema` | single `exec_depend` on `nodl_schema` |
| `ros2nodl` | `depend` on `nodl_schema` only | unchanged |

The only breaking change is the `find_package` / `package.xml` name. Macro
names, Python API, and CLI are all unchanged.

## Alternatives Considered

### Keep both packages, extract integration tests into a third package

Create a `nodl_integration_tests` package that depends on both and owns the
cross-cutting tests. This breaks the cycle but adds a package that exists
solely to test the interaction between two packages that have a 1:1
relationship. It treats the symptom (circular test dep) without addressing
the cause (wrong package boundary).

### Keep both packages, skip tests when the other isn't available

Remove the `test_depend` and use `pytest.mark.skipif` to conditionally skip
integration tests. This hides the cycle but means the tests silently don't
run if someone forgets to source the workspace — a footgun that undermines
the point of having the tests.

### Merge into `ament_nodl` instead

Use `ament_nodl` as the surviving package name. This would follow the
`ament_*` naming convention for packages providing CMake macros, but it
misrepresents the package's primary purpose. `nodl_schema` is used by pure
Python consumers (`ros2nodl`, codegen backends) that have no CMake involvement.
Forcing them to depend on something called `ament_nodl` is misleading.
The `ament_nodl_*()` macro names are sufficient to signal ament integration
at the CMake API level without the package itself being named `ament_*`.
