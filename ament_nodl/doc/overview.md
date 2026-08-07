# ament_nodl

`ament_nodl` provides CMake macros for registering a node's NoDL document with the ament resource index, so other
tools can locate a node's interface specification by package and executable name.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## `ament_nodl_register_node`

Register a NoDL document for an executable. This does three things:

1. Validates the file at build time (via `python -m nodl_schema`), so authoring errors surface when registering
   rather than downstream when a consumer reads the spec.
   If the document uses `include`, this step also checks that its references resolve.
2. Installs the file into the ament index under the `nodl_nodes` resource type, keyed `<package>__<executable>`.
3. Installs the file under `share/<package>/nodl/` for direct filesystem access.

```cmake
find_package(ament_nodl REQUIRED)

ament_nodl_register_node(my_node
  FILE nodl/my_node.nodl.yaml
)
```

### Includes and build order

A `nodl://<package>/<name>` reference resolves through the ament index, which holds what is *installed*.
Validation runs before this package is installed, so a referenced package must already be built and be a dependency of this one.
Note: it is therefore not (yet) possible at build time for a document to reference another document in its own package.
This feature is upcoming in a followup pass.

`python -m nodl_schema <file> --no-resolve` checks the schema without following references, if you need it.

### Arguments

:`executable_name`: Name of the executable the document describes. Combined with `PACKAGE` to form the resource key.
:`FILE`: Path to the NoDL file. Absolute, or relative to `CMAKE_CURRENT_SOURCE_DIR`. Required.
:`PACKAGE`: Package name used in the resource key. Defaults to `${PROJECT_NAME}`.

See the macro source at {repo}`ament_nodl/cmake/ament_nodl_register_node.cmake`.

## Consuming registered documents

Tools retrieve a registered document by its resource key:

```python
from ament_index_python.packages import get_resource

content, path = get_resource('nodl_nodes', 'my_package__my_node')
```

The validation step shells out to `nodl_schema`, which is this package's runtime dependency.
