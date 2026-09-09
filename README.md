# NoDL - Node Definition Language

[![Rolling Dev](https://build.ros2.org/job/Rdev__nodl__ubuntu_resolute_amd64/badge/icon?subject=rolling-dev)](https://build.ros2.org/job/Rdev__nodl__ubuntu_resolute_amd64/)
[![Lyrical Dev](https://build.ros2.org/job/Ldev__nodl__ubuntu_resolute_amd64/badge/icon?subject=lyrical-dev)](https://build.ros2.org/job/Ldev__nodl__ubuntu_resolute_amd64/)
[![Kilted Dev](https://build.ros2.org/job/Kdev__nodl__ubuntu_noble_amd64/badge/icon?subject=kilted-dev)](https://build.ros2.org/job/Kdev__nodl__ubuntu_noble_amd64/)
[![Jazzy Dev](https://build.ros2.org/job/Jdev__nodl__ubuntu_noble_amd64/badge/icon?subject=jazzy-dev)](https://build.ros2.org/job/Jdev__nodl__ubuntu_noble_amd64/)
[![Humble Dev](https://build.ros2.org/job/Hdev__nodl__ubuntu_jammy_amd64/badge/icon?subject=humble-dev)](https://build.ros2.org/job/Hdev__nodl__ubuntu_jammy_amd64/)

[![Rolling Doc](https://build.ros2.org/job/Rdoc__nodl__ubuntu_resolute_amd64/badge/icon?subject=rolling-doc)](https://build.ros2.org/job/Rdoc__nodl__ubuntu_resolute_amd64/)
[![Lyrical Doc](https://build.ros2.org/job/Ldoc__nodl__ubuntu_resolute_amd64/badge/icon?subject=lyrical-doc)](https://build.ros2.org/job/Ldoc__nodl__ubuntu_resolute_amd64/)
[![Kilted Doc](https://build.ros2.org/job/Kdoc__nodl__ubuntu_noble_amd64/badge/icon?subject=kilted-doc)](https://build.ros2.org/job/Kdoc__nodl__ubuntu_noble_amd64/)
[![Jazzy Doc](https://build.ros2.org/job/Jdoc__nodl__ubuntu_noble_amd64/badge/icon?subject=jazzy-doc)](https://build.ros2.org/job/Jdoc__nodl__ubuntu_noble_amd64/)
[![Humble Doc](https://build.ros2.org/job/Hdoc__nodl__ubuntu_jammy_amd64/badge/icon?subject=humble-doc)](https://build.ros2.org/job/Hdoc__nodl__ubuntu_jammy_amd64/)

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

### Pip dependencies for full test suite

The packages in this repository use a few package only available from `pip` as `test_depend`s.

For the buildfarm environment, these dependencies and tests are disabled, because a package may not be packaged into a `deb`/`rpm` against dependencies from another package manager (`pip`).

To install all dependencies and run the full test suite, export environment variable `ENABLE_PIP_TEST_DEPENDS=1` - which the GitHub Action CI for this repo does.
