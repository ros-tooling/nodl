# ament_nodl

`ament_nodl` provides CMake integration for registering NoDL documents
and checking a live node against one during `colcon test`.

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
It generates a launch test in the build tree, launches the target node, and
calls `ros2nodl.conformance.assert_conforms`.

See the macro source at
{repo}`ament_nodl/cmake/nodl_add_conformance_test.cmake`.

## Consuming registered documents

Tools retrieve a registered document by its resource key:

```python
from ament_index_python.packages import get_resource

content, path = get_resource('nodl', 'my_package__my_node')
```
