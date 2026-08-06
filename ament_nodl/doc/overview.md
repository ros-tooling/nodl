# ament_nodl

`ament_nodl` provides CMake macros for registering a node's NoDL document with the ament resource index, so other
tools can locate a node's interface specification by package and executable name.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## `ament_nodl_register_node`

Register a NoDL document for an executable. This does three things:

1. Validates the file at build time, so authoring errors surface when registering rather than downstream when a consumer reads it.
   If the document uses `include`, this step also checks that references resolve correctly.
   Because validation runs before install, an included `nodl://<package>/<name>` must belong to a package that is already built and a dependency of this one.
2. Rewrites relative `include` references to `nodl://<package>/<name>`, if the document has any.
   A document without them is installed exactly as authored.
3. Installs the result into the ament index under the `nodl_nodes` resource type, keyed `<package>__<executable>`, and under `share/<package>/nodl/` for direct filesystem access.

```cmake
find_package(ament_nodl REQUIRED)

ament_nodl_register_node(my_node
  FILE nodl/my_node.nodl.yaml
)
```

### Relative includes

A document may reference another document in the same package by relative path, which is the only form that can reach a
document in the package being built. Such a reference means nothing to a consumer reading the document back out of the
index, which gets text and no path to resolve against, so registration rewrites it to the name the referenced document
was registered under.

That name has to exist, so **the referenced document must be registered first**:

```cmake
# telemetry.nodl.yaml first: composed_node references it by path, and the rewrite needs its name.
ament_nodl_register_node(telemetry FILE nodl/common/telemetry.nodl.yaml)
ament_nodl_register_node(composed_node FILE nodl/composed_node.nodl.yaml)
```

With `composed_node.nodl.yaml` authored as:

```yaml
nodl_version: 2
include:
  - ref: common/telemetry.nodl.yaml
```

what installs is that same document with the reference reading `nodl://<package>/telemetry`.

Two mistakes are caught when CMake configures rather than later:

- Referencing a document that no earlier `ament_nodl_register_node` call registered. There is no name to rewrite to.
- Registering one name from two different files. The second would take over a name that an already-rewritten reference
  points at.

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
