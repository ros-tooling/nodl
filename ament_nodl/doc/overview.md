# ament_nodl

`ament_nodl` provides CMake integration for registering a node's NoDL document
and checking a live node against it during `colcon test`.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## `ament_nodl_register`

Register a NoDL document with the ament index. This does three things:

1. Validates the file at build time so authoring errors surface when registering rather than downstream when a consumer reads the spec.
   If the document uses `include`, this step also checks that its references resolve.
2. Installs the file into the ament index under the `nodl` resource type, keyed `<package>__<name>`.
3. Installs the file under `share/<package>/nodl/` for direct filesystem access.

```cmake
find_package(ament_nodl REQUIRED)

ament_nodl_register(my_node
  FILE nodl/my_node.nodl.yaml
)
```

### Includes and build order

A `nodl://<package>/<name>` reference resolves through the ament index, which holds what is *installed*.
Validation runs before this package is installed, so a referenced package must already be built and be a dependency of this one.

### Arguments

:`executable_name`: Name of the executable the document describes. Combined with `PACKAGE` to form the resource key.
:`FILE`: Path to the NoDL file. Absolute, or relative to `CMAKE_CURRENT_SOURCE_DIR`. Required.
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
