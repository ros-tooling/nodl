# NoDL

NoDL (Node Definition Language) is a schema and toolkit to describe a ROS 2 node's interface: parameters, topics (publishers and subscriptions), services (clients and servers), and actions (clients and servers).

:::{note}
**Status: v2 development.** The schema and APIs are not yet stable. Expect breaking changes until v2 is announced for distribution.
:::

## Documentation

```{toctree}
:maxdepth: 2

Home <self>
why-nodl
concepts
schema
documenting
roadmap
tutorials/index
```

## Packages

- **`nodl`** - the entrypoint metapackage containing core documentation and dependency on subpackages.
  It is documented by this top-level site and has no separate page.
- **`nodl_schema`** — the NoDL Schema. Provides a Python-based document validator and typed object data model for working with schema objects.
- **`nodl_observe`** — observe a running node and produce its runtime description as a `rosgraph_msgs/Node` message; the library behind `ros2 nodl describe`.
- **`ros2nodl`** — `ros2 nodl <verb>` ros2cli extension providing NoDL operations.
  See the [Describe guide](_generated/packages/ros2nodl/describe.md).
- **`ament_nodl`** — CMake integration for registering NoDL documents and checking live-node conformance with `colcon test`.
- **`nodl_common_interfaces`** — NoDL descriptions for standard ROS 2 node base classes (`rclcpp::Node`, `rclcpp_lifecycle::LifecycleNode`), registered in the ament index until upstream ships its own.
- **`nodl_generator_cpp`** — C++ code generation from NoDL documents: generates an abstract base class with all endpoint wiring, delegating parameters to `generate_parameter_library`.
- **`nodl_docgen`** — Tools to generate documentation from NoDL documents.
- **`nodl_conformance`** — semantic comparison of two loaded NoDL documents.
  `ros2nodl` provides runtime conformance checks for live nodes.

Each package's own documentation is staged into this site from its `doc/` tree at build time
(see {repo}`nodl/doc/package_docs.py`); the same sources build standalone under `rosdoc2` for docs.ros.org.

```{toctree}
:maxdepth: 1
:caption: Packages

nodl_schema <_generated/packages/nodl_schema/overview>
nodl_observe <_generated/packages/nodl_observe/overview>
ros2nodl <_generated/packages/ros2nodl/overview>
ament_nodl <_generated/packages/ament_nodl/overview>
nodl_common_interfaces <_generated/packages/nodl_common_interfaces/overview>
nodl_generator_cpp <_generated/packages/nodl_generator_cpp/overview>
nodl_docgen <_generated/packages/nodl_docgen/overview>
nodl_conformance <_generated/packages/nodl_conformance/overview>
```

## Source

Repository: <https://github.com/ros-tooling/nodl>
