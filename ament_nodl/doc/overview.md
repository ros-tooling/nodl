# ament_nodl

`ament_nodl` provides CMake integration for registering a node's NoDL document
and checking a live node against it during `colcon test`.

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

:`executable_name`: Name of the executable the document describes. Combined with `PACKAGE` to form the resource key, which must be unique.
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
    NODE_NAME my_node
    NODE_NAMESPACE /robot
    TIMEOUT 15
  )
endif()
```

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
:`NODE_NAME`: Node name passed to the executable and used to construct its fully qualified name. Required.
:`PACKAGE`: Package containing the executable. Defaults to `${PROJECT_NAME}`.
:`NODE_NAMESPACE`: Namespace passed to the executable. Defaults to `/`.
:`TIMEOUT`: Maximum time in seconds for the conformance check. Defaults to 15 and must be a positive integer.

### Behavior

The macro rejects a missing file during CMake configuration.
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
