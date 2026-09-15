# NoDL - Node Definition Language

<img src="nodl/doc/nodl_logo.png" alt="NoDL logo" width="300">

NoDL (Node Definition Language) is a schema and toolkit to describe a ROS 2 node's interface: parameters, topics (publishers and subscriptions), services (clients and servers), and actions (clients and servers).

Find complete documentation at https://nodl.readthedocs.io/en/latest/

## Repository structure

- [ament_nodl/](./ament_nodl/): CMake macros to register NoDL documents with the ament index
- [nodl/](./nodl/): Metapackage that pulls in the other packages as dependencies. Acts as an easy default for those who don't want a-la-carte.
  - [doc/](./nodl/doc/): Documentation source for the ReadTheDocs page
- [nodl_common_interfaces/](./nodl_common_interfaces/): NoDL descriptions for standard ROS 2 node base classes (`rclcpp::Node`, `rclcpp_lifecycle::LifecycleNode`, `rclpy.node.Node`, and `rclpy.lifecycle.LifecycleNode`), registered in the ament index until upstream ships its own.
- [nodl_docgen/](./nodl_docgen/): Sphinx extension rendering a NoDL document into a documentation page at build time.
- [nodl_generator_common/](./nodl_generator_common/): Language-agnostic code-generation core shared by NoDL generators — include-tree provenance, entity filtering, ament dependency emission, and naming utilities.
- [nodl_generator_cpp/](./nodl_generator_cpp/): C++ code generator — produces an abstract base class from a NoDL document, with a CMake macro for build integration.
- [nodl_generator_py/](./nodl_generator_py/): Python code generator — produces an `rclpy` base class from a NoDL document at build time.
- [nodl_observe/](./nodl_observe/): C++ (`ament_cmake`) package that observes a running ROS 2 node and produces its runtime interface as a `rosgraph_msgs/Node` message — a reusable `observe_node(...)` library plus an `observe` executable. Stage one of Observe → Describe.
- [nodl_schema/](./nodl_schema/): Package providing the NoDL schema, validation tools, a typed data model, and semantic comparison of loaded documents.
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

### Pip dependencies for full test suite

The packages in this repository use a few package only available from `pip` as `test_depend`s.

For the buildfarm environment, these dependencies and tests are disabled, because a package may not be packaged into a `deb`/`rpm` against dependencies from another package manager (`pip`).

To install all dependencies and run the full test suite, export environment variable `ENABLE_PIP_TEST_DEPENDS=1` - which the GitHub Action CI for this repo does.

## Buildfarm Status

| Distro | Dev | Doc | Ubuntu Bin |
|--------|-----|-----|-----------|
| Humble | [![Hdev](https://build.ros2.org/job/Hdev__nodl__ubuntu_jammy_amd64/badge/icon?subject=Hdev)](https://build.ros2.org/job/Hdev__nodl__ubuntu_jammy_amd64/) | [![Hdoc](https://build.ros2.org/job/Hdoc__nodl__ubuntu_jammy_amd64/badge/icon?subject=Hdoc)](https://build.ros2.org/job/Hdoc__nodl__ubuntu_jammy_amd64/) | [![Hbin](https://build.ros2.org/job/Hbin_uJ64__nodl__ubuntu_jammy_amd64__binary/badge/icon?subject=Hbin)](https://build.ros2.org/job/Hbin_uJ64__nodl__ubuntu_jammy_amd64__binary/) |
| Jazzy | [![Jdev](https://build.ros2.org/job/Jdev__nodl__ubuntu_noble_amd64/badge/icon?subject=Jdev)](https://build.ros2.org/job/Jdev__nodl__ubuntu_noble_amd64/) | [![Jdoc](https://build.ros2.org/job/Jdoc__nodl__ubuntu_noble_amd64/badge/icon?subject=Jdoc)](https://build.ros2.org/job/Jdoc__nodl__ubuntu_noble_amd64/) | [![Jbin](https://build.ros2.org/job/Jbin_uN64__nodl__ubuntu_noble_amd64__binary/badge/icon?subject=Jbin)](https://build.ros2.org/job/Jbin_uN64__nodl__ubuntu_noble_amd64__binary/) |
| Kilted | [![Kdev](https://build.ros2.org/job/Kdev__nodl__ubuntu_noble_amd64/badge/icon?subject=Kdev)](https://build.ros2.org/job/Kdev__nodl__ubuntu_noble_amd64/) | [![Kdoc](https://build.ros2.org/job/Kdoc__nodl__ubuntu_noble_amd64/badge/icon?subject=Kdoc)](https://build.ros2.org/job/Kdoc__nodl__ubuntu_noble_amd64/) | [![Kbin](https://build.ros2.org/job/Kbin_uN64__nodl__ubuntu_noble_amd64__binary/badge/icon?subject=Kbin)](https://build.ros2.org/job/Kbin_uN64__nodl__ubuntu_noble_amd64__binary/) |
| Lyrical | [![Ldev](https://build.ros2.org/job/Ldev__nodl__ubuntu_resolute_amd64/badge/icon?subject=Ldev)](https://build.ros2.org/job/Ldev__nodl__ubuntu_resolute_amd64/) | [![Ldoc](https://build.ros2.org/job/Ldoc__nodl__ubuntu_resolute_amd64/badge/icon?subject=Ldoc)](https://build.ros2.org/job/Ldoc__nodl__ubuntu_resolute_amd64/) | [![Lbin](https://build.ros2.org/job/Lbin_uR64__nodl__ubuntu_resolute_amd64__binary/badge/icon?subject=Lbin)](https://build.ros2.org/job/Lbin_uR64__nodl__ubuntu_resolute_amd64__binary/) |
| Rolling | [![Rdev](https://build.ros2.org/job/Rdev__nodl__ubuntu_resolute_amd64/badge/icon?subject=Rdev)](https://build.ros2.org/job/Rdev__nodl__ubuntu_resolute_amd64/) | [![Rdoc](https://build.ros2.org/job/Rdoc__nodl__ubuntu_resolute_amd64/badge/icon?subject=Rdoc)](https://build.ros2.org/job/Rdoc__nodl__ubuntu_resolute_amd64/) | [![Rbin](https://build.ros2.org/job/Rbin_uR64__nodl__ubuntu_resolute_amd64__binary/badge/icon?subject=Rbin)](https://build.ros2.org/job/Rbin_uR64__nodl__ubuntu_resolute_amd64__binary/) |
