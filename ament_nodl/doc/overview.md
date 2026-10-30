# ament_nodl

`ament_nodl` provides CMake integration for registering NoDL documents
and checking a live node against one during `colcon test`.
Packages that do not build with CMake, such as `ament_python` packages, add the same check with a Python helper.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## `ament_nodl_register`

Register a NoDL document with the ament index. This does three things:

1. Validates the file at build time so authoring errors surface when registering rather than downstream when a consumer reads the spec.
   If the document uses `include`, this step also checks that its references resolve.
2. Installs the file into the ament index under the `nodl` resource type, keyed `<package>__<name>`.
3. Installs the file as `share/<package>/nodl/<name>.nodl.yaml` for direct filesystem access.
   The copy is named after the resource, not the source file, so files with the same name in different directories do not overwrite each other.
   It is always YAML, whatever the source format.

```cmake
find_package(ament_nodl REQUIRED)

ament_nodl_register(my_node
  FILE nodl/my_node.nodl.yaml
)
```

### Includes and build order

A `nodl://<package>/<name>` reference resolves through the ament index, which holds what is *installed*.
Validation runs before this package is installed, so a referenced package must already be built and be a dependency of this one.

### Local includes

A `local://` include in a registered document is rewritten to a `nodl://<package>/<name>` reference on install.
The included file must therefore be registered with `ament_nodl_register` as well.
Configuration fails if it is not, naming the registered document and the missing include.
The check reruns whenever a registered document changes.

### Subdirectories

`ament_nodl_register` can be called from any CMake directory of the project.
Rewriting and installing run once per project, at the end of the `CMakeLists.txt` that calls `project()`, with every registration known.
When the package is added to a larger build with `add_subdirectory`, that is the package's own `CMakeLists.txt`, not the root of the larger build.
A subdirectory that calls `project()` starts its own set of registrations.
A document can therefore include one registered from another directory, regardless of registration order.

### Unique names and files

Each `<package>__<name>` resource key can be registered only once, and configuration fails with an error naming the key otherwise.
Each file can also be registered under only one name.
A second name for the same file would add a second rewrite rule for one path, so the `nodl://` reference its includers receive would be ambiguous.

### Arguments

:`resource_name`: Name of the registered document within its package.
  Combined with `PACKAGE` to form the resource key, which must be unique.
:`FILE`: Path to the NoDL file. Absolute, or relative to `CMAKE_CURRENT_SOURCE_DIR`. Required.
  Each file can be registered once.
:`PACKAGE`: Package name used in the resource key. Defaults to `${PROJECT_NAME}`.

See the macro source at {repo}`ament_nodl/cmake/ament_nodl_register.cmake`.

## `nodl_add_conformance_test`

Register a launch test that starts one ROS 2 executable and checks it against
one explicit NoDL document.
The test runs with `colcon test`; it does not affect normal node execution.

Add the test dependencies to `package.xml`:

```xml
<test_depend>ament_nodl</test_depend>
```

Register the test inside the package's `BUILD_TESTING` block:

```cmake
if(BUILD_TESTING)
  find_package(ament_nodl REQUIRED)

  nodl_add_conformance_test(my_node_conformance
    EXECUTABLE my_node
    NODL_FILE nodl/my_node.nodl.yaml
    NODE_NAMESPACE /robot
    TIMEOUT 15
  )
endif()
```

Nodes with required parameters that have no default need them passed to start:

```cmake
  nodl_add_conformance_test(my_node_conformance
    EXECUTABLE my_node
    NODL_FILE nodl/my_node.nodl.yaml
    PARAMETERS_FILE config/my_node.yaml
    PARAMETERS limit:=5 "frame_id:=base link"
  )
```

### Ignoring endpoints

The check fails on any endpoint that the document does not declare.
Declaring every endpoint in the document is the goal.
Ignore rules cover two cases:

- **Environment injection.**
  The runtime environment adds an endpoint to every node, which no node document can declare.
  Specifically, `rmw_stats_shim` adds a `/topic_statistics` publisher at the RMW layer, and no other such case is known.
  Set these rules once in `NODL_CONFORMANCE_IGNORE`, next to the environment that injects the endpoint.
- **Partial adoption.**
  A node's helpers, mixins or plugins contribute endpoints that NoDL does not model yet.
  Document the node's own interface and ignore the known contributed endpoints, so the test passes during adoption.
  This is an on-ramp and not a destination, because the contributed endpoints stay unverified until they are declared.
  Pass these rules with `IGNORE`, because they are specific to one node.

Keep rules as narrow as possible, with exact names rather than broad globs where practical.
`IGNORE` lists rules that leave observed endpoints out of the comparison:

```cmake
nodl_add_conformance_test(my_node_conformance
  EXECUTABLE my_node
  NODL_FILE nodl/my_node.nodl.yaml
  IGNORE publisher:/topic_statistics
)
```

A rule is `KIND:NAME` or `KIND:NAME:TYPE`, where `NAME` and `TYPE` are globs.
It only drops endpoints that the document does not declare.
Rules in the `NODL_CONFORMANCE_IGNORE` environment variable apply to every conformance test when it runs, so a project can set the rules for environment-injected endpoints once.
See the `ros2nodl` conform guide for the full rule syntax.

### Running the test

After building the package, run the conformance test with its other tests:

```console
colcon test --packages-select my_package
colcon test-result --verbose
```

### Arguments

:`test_name`: Name of the registered launch test. Required.
:`EXECUTABLE`: Name of the ROS 2 executable to launch. Required.
:`NODL_FILE`: Path to the expected NoDL document. Absolute, or relative to `CMAKE_CURRENT_SOURCE_DIR`. Required.
:`NODE_NAME`: Node name passed to the executable and used to construct its fully qualified name. Defaults to `test_name`. Pass it when `test_name` is not a valid node name (letters, digits and underscores, not starting with a digit).
:`PACKAGE`: Package containing the executable. Defaults to `${PROJECT_NAME}`.
:`NODE_NAMESPACE`: Namespace passed to the executable. Defaults to `/`.
:`TIMEOUT`: Maximum time in seconds for the conformance check. Defaults to 15 and must be a positive integer.
:`PARAMETERS`: Parameters passed to the node as `name:=value` items, with the same syntax as `ros2 run -p`.
  Items are applied after `PARAMETERS_FILE` and override the same parameter set there.
:`PARAMETERS_FILE`: YAML parameter files passed to the node. Each is absolute, or relative to `CMAKE_CURRENT_SOURCE_DIR`.
:`IGNORE`: Zero or more ignore rules, passed to `assert_conforms` as `ignore`.

### Behavior

The macro rejects a missing `NODL_FILE` or `PARAMETERS_FILE`, a `PARAMETERS` item that is not `name:=value`, and an invalid default node name, during CMake configuration.
It generates a launch test in the build tree that calls {ref}`conformance_test <ament-nodl-python-packages>`, which launches the target node and calls `ros2nodl.conformance.assert_conforms`.

See the macro source at
{repo}`ament_nodl/cmake/nodl_add_conformance_test.cmake`.
A package that cannot call CMake gets the same test from {ref}`conformance_test <ament-nodl-python-packages>`.

(ament-nodl-python-packages)=

## Python packages

An `ament_python` package cannot call `nodl_add_conformance_test`, so a test module calls `ament_nodl.testing.conformance_test` instead.
It starts the executable and checks the running node against the document, with the same options and defaults as the macro.
The macro generates its test from the same function.

Add the test dependency to `package.xml`:

```xml
<test_depend>ament_nodl</test_depend>
```

`colcon` runs `pytest` for an `ament_python` package only if the package declares it where `colcon` looks, such as `extras_require={'test': ['pytest']}` in `setup.py`.
Without it, `colcon test` skips the test.

Create a test module, such as `test/test_conformance.py`, that assigns the two names `launch_testing` looks for:

```{literalinclude} examples/test_conformance.py
:language: python
:start-at: from ament_nodl.testing
```

The example runs against the fixture node of `test_ament_nodl`.
In your package, `package` and `executable` name the executable that your `setup.cfg` or `setup.py` installs.
`pytest` runs it with the package's other tests, such as `colcon test --packages-select my_package`, and `launch_testing`'s `launch_test` command runs it as well.

The `nodl` argument names the document, in one of two forms, as the `nodl-node` directive of `nodl_docgen` takes its argument.
A **path** is absolute, and is usually built from the test file, such as `nodl=Path(__file__).parent / 'nodl' / 'my_node.nodl.yaml'`.
A **reference** is a `nodl://<package>/<name>` string, which `nodl_schema`'s registered resolvers resolve through the ament index.
The document must be installed before the test runs, and it can come from a different package than the executable.

The call checks its arguments, the files they name and the reference when the module is imported.
A mistake raises there, and `pytest` reports a collection error that interrupts that package's whole test session, not only this test.

### Differences from the macro

The macro names a node after the test, and the Python helper names it after the executable.
Pass `node_name` when the executable is not a valid node name.
Paths must be absolute, because a test module has no source directory like `CMAKE_CURRENT_SOURCE_DIR` to resolve against.
`package` is required, because there is no `PROJECT_NAME`.

### Arguments

All arguments are keywords.

:`package`: Package containing the executable. Required.
:`executable`: Name of the ROS 2 executable to launch. Required.
:`nodl`: The expected NoDL document, as an absolute path or a `nodl://<package>/<name>` reference. Required.
:`node_name`: Node name passed to the executable and used to construct its fully qualified name. Defaults to `executable`.
:`node_namespace`: Namespace passed to the executable. Defaults to `/`.
:`timeout`: Maximum time in seconds for the conformance check, a positive integer. Defaults to 15.
:`parameters`: List of `name:=value` items passed to the node as `-p` arguments, applied after `parameters_files`.
:`parameters_files`: List of absolute paths of YAML parameter files passed to the node.
:`ignore`: List of ignore rules, as for `IGNORE` of the macro.
  Rules in `NODL_CONFORMANCE_IGNORE` apply as well, after these.

The function returns `(generate_test_description, TestNodlConformance)`, both named after the module that calls it.
`generate_test_description` carries the `launch_test` marker, without which `pytest` runs the test case and launches nothing.

See the module source at {repo}`ament_nodl/ament_nodl/testing.py`.

## Consuming registered documents

Tools retrieve a registered document by its resource key:

```python
from ament_index_python.packages import get_resource

content, path = get_resource('nodl', 'my_package__my_node')
```
