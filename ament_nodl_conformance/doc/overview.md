# ament_nodl_conformance

`ament_nodl_conformance` provides optional CMake and launch-test integration for
checking one ROS 2 executable against one explicit NoDL document.

Add the test dependency to `package.xml`:

```xml
<test_depend>ament_nodl_conformance</test_depend>
```

Register the test inside the package's `BUILD_TESTING` block:

```cmake
if(BUILD_TESTING)
  find_package(ament_nodl_conformance REQUIRED)

  nodl_add_conformance_test(my_node_conformance
    EXECUTABLE my_node
    NODL_FILE nodl/my_node.nodl.yaml
    NODE_NAME my_node
    NODE_NAMESPACE /robot
    TIMEOUT 15
  )
endif()
```

`EXECUTABLE`, `NODL_FILE`, and `NODE_NAME` are required. `PACKAGE` defaults to
`${PROJECT_NAME}`. `NODE_NAMESPACE` defaults to `/`. `TIMEOUT` defaults to 15
seconds and must be a positive integer.

`NODL_FILE` can be absolute or relative to the current source directory. The
macro rejects a missing file during CMake configuration. It generates a launch
test in the build tree, launches the target node, and calls
`ros2nodl.conformance.assert_conforms`.

The macro source is at
{repo}`ament_nodl_conformance/cmake/nodl_add_conformance_test.cmake`.
