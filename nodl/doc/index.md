# NoDL

NoDL (Node Definition Language) is a schema and toolkit to describe a ROS 2 node's interface: parameters, topics (publishers and subscriptions), services (clients and servers), and actions (clients and servers).

:::{note}
**Status: v2 development.** The schema and APIs are not yet stable. Expect breaking changes until v2 is announced for distribution.
:::

## Documentation

```{toctree}
:maxdepth: 2

Home <self>
concepts
schema
roadmap
```

## Packages

- **`nodl`** - the entrypoint metapackage containing core documentation and dependency on subpackages.
  It is documented by this top-level site and has no separate page.
- **`nodl_schema`** — the NoDL Schema. Provides a Python-based document validator and typed object data model for working with schema objects.
- **`ros2nodl`** — `ros2 nodl <verb>` ros2cli extension providing NoDL operations.
- **`ament_nodl`** — CMake macros for registering NoDL documents with the ament index.

Each package's own documentation is staged into this site from its `doc/` tree at build time
(see {repo}`nodl/doc/package_docs.py`); the same sources build standalone under `rosdoc2` for docs.ros.org.

```{toctree}
:maxdepth: 1
:caption: Packages

nodl_schema <_generated/packages/nodl_schema/index>
ros2nodl <_generated/packages/ros2nodl/index>
ament_nodl <_generated/packages/ament_nodl/index>
```

## Source

Repository: <https://github.com/ros-tooling/nodl>
