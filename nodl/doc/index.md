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
roadmap
tutorials/index
```

## Packages

NoDL is a language for defining ROS nodes, but the NoDL Project comprises a variety of packages built for different features around using NoDL documents.
Documentation for these packages is available:

**`nodl`**: the entrypoint metapackage that collects together the common NoDL packages, and provides this core documentation.

- [`ament_nodl`](_generated/packages/ament_nodl/overview) — CMake integration for registering NoDL documents and checking live-node conformance with `colcon test`.
- [`nodl_common_interfaces`](_generated/packages/nodl_common_interfaces/overview) — NoDL descriptions for standard ROS 2 node base classes (`rclcpp::Node`, `rclcpp_lifecycle::LifecycleNode`, `rclpy.node.Node`, and `rclpy.lifecycle.LifecycleNode`), registered in the ament index until upstream ships its own.
- [`nodl_docgen`](_generated/packages/nodl_docgen/overview) — Tools to generate documentation from NoDL documents.
- [`nodl_generator_common`](_generated/packages/nodl_generator_common/overview) — language-agnostic code-generation core shared by NoDL generators: include-tree provenance, entity filtering, ament dependency emission, and naming utilities.
- [`nodl_generator_cpp`](_generated/packages/nodl_generator_cpp/overview) — C++ code generation from NoDL documents: generates an abstract base class with all endpoint wiring, delegating parameters to `generate_parameter_library`.
- [`nodl_generator_py`](_generated/packages/nodl_generator_py/overview) — Python code generation from NoDL documents: generates an `rclpy` base class at build time.
- [`nodl_observe`](_generated/packages/nodl_observe/overview) — observe a running node and produce its runtime description as a `rosgraph_msgs/Node` message; the library behind `ros2 nodl describe`.
- [`nodl_schema`](_generated/packages/nodl_schema/overview) — the NoDL Schema. Provides a Python-based document validator and typed object data model for working with schema objects.
- [`ros2nodl`](_generated/packages/nodl_observe/overview) — `ros2 nodl <verb>` ros2cli extension providing NoDL operations.
  See the [Describe guide](_generated/packages/ros2nodl/describe.md).
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
nodl_schema <_generated/packages/nodl_schema/overview>
ros2nodl <_generated/packages/ros2nodl/overview>
```

## Source

Repository: <https://github.com/ros-tooling/nodl>
