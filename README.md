# NoDL - Node Definition Language

<img src="nodl/doc/nodl_logo.png" alt="NoDL logo" width="300">

NoDL (Node Definition Language) is a schema and toolkit to describe a ROS 2 node's interface: parameters, topics (publishers and subscriptions), services (clients and servers), and actions (clients and servers).

Find complete documentation at https://nodl.readthedocs.io/en/latest/

## Repository structure

- [ament_nodl/](./ament_nodl/): CMake macros to register NoDL documents with the ament index
- [nodl/](./nodl/): Metapackage that pulls in the other packages as dependencies. Acts as an easy default for those who don't want a-la-carte.
  - [doc/](./nodl/doc/): Documentation source for the ReadTheDocs page
- [nodl_common_interfaces/](./nodl_common_interfaces/): NoDL descriptions for standard ROS 2 node base classes (`rclcpp::Node`, `rclcpp_lifecycle::LifecycleNode`), registered in the ament index until upstream ships its own.
- [nodl_docgen/](./nodl_docgen/): Sphinx extension rendering a NoDL document into a documentation page at build time.
- [nodl_generator_cpp/](./nodl_generator_cpp/): C++ code generator — produces an abstract base class from a NoDL document, with a CMake macro for build integration.
- [nodl_observe/](./nodl_observe/): C++ (`ament_cmake`) package that observes a running ROS 2 node and produces its runtime interface as a `rosgraph_msgs/Node` message — a reusable `observe_node(...)` library plus an `observe` executable. Stage one of Observe → Describe.
- [nodl_schema/](./nodl_schema/): Package providing the NoDL schema, plus a Python package with validation tools and typed data model to work with it.
    [nodl.schema.yaml](./nodl_schema/nodl_schema/schemas/nodl.schema.yaml): The NoDL schema, key to this whole thing!
- [ros2nodl/](./ros2nodl/): `ros2cli` extension providing `ros2 nodl ...` commands
- [test_nodl_generator_cpp/](./test_nodl_generator_cpp/): Integration tests for `nodl_generator_cpp` — exercises the CMake macro end-to-end.
- [tools/](./tools/): Scripts supporting development and build workflows

## Developing

### Setup

1. Clone the repo and install pre-commit hooks:

```bash
pre-commit install
pre-commit install --hook-type prepare-commit-msg
```

The `prepare-commit-msg` hook will automatically add the `Signed-off-by` line to your commits. If you prefer to sign off manually, use `git commit -s`.
