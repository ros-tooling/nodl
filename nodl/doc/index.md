# NoDL

NoDL (Node Definition Language) is a schema and toolkit to describe a ROS 2 node's interface: parameters, topics (publishers and subscriptions), services (clients and servers), and actions (clients and servers).

:::{note}
**Status: v2 is out!**
The schema and APIs are reasonably stable, and we believe NoDL is ready for early adoption.
:::

## Documentation

```{toctree}
:maxdepth: 2

Home <self>
why-nodl
concepts
schema
documenting
CMake API <_generated/cmake/index>
roadmap
tutorials/index
```

## Packages

NoDL is a language for defining ROS nodes, but the NoDL Project comprises a variety of packages built for different features around using NoDL documents.
Documentation for these packages is available:

**`nodl`**: {package-description}`nodl` This site is its core documentation.

```{package-list}
```

Each package's own documentation is staged into this site from its `doc/` tree at build time
(see {repo}`nodl/doc/package_docs.py`); the same sources build standalone under `rosdoc2` for docs.ros.org.

```{toctree}
:maxdepth: 1
:caption: Packages
:hidden:

ament_nodl <_generated/packages/ament_nodl/overview>
nodl_common_interfaces <_generated/packages/nodl_common_interfaces/overview>
nodl_docgen <_generated/packages/nodl_docgen/overview>
nodl_generator_common <_generated/packages/nodl_generator_common/overview>
nodl_generator_cpp <_generated/packages/nodl_generator_cpp/overview>
nodl_generator_py <_generated/packages/nodl_generator_py/overview>
nodl_observe <_generated/packages/nodl_observe/overview>
nodl_runtime_py <_generated/packages/nodl_runtime_py/overview>
nodl_schema <_generated/packages/nodl_schema/overview>
ros2nodl <_generated/packages/ros2nodl/overview>
```

## Source

Repository: <https://github.com/ros-tooling/nodl>
