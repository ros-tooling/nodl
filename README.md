# NoDL - Node Definition Language

<img src="nodl/doc/nodl_logo.png" alt="NoDL logo" width="300">

NoDL (Node Definition Language) is a schema and toolkit to describe a ROS 2 node's interface: parameters, topics (publishers and subscriptions), services (clients and servers), and actions (clients and servers).

Find complete documentation at https://nodl.readthedocs.io/en/latest/

## Repository structure

NoDL is split into packages for the schema, code generators, documentation generation, and ROS 2 integration.
The [`nodl`](./nodl/) metapackage pulls in the common ones, so most users only need to depend on it.
The [package list](https://nodl.readthedocs.io/en/latest/#packages) in the documentation describes each package.

The NoDL schema, key to this whole thing, is [nodl.schema.yaml](./nodl_schema/nodl_schema/schemas/nodl.schema.yaml).

Outside the packages:

- [design/](./design/): Design documents for NoDL features
- [examples/](./examples/): Example packages that the tutorials build on
- [nodl/doc/](./nodl/doc/): Documentation source for the ReadTheDocs page
- [test_ament_nodl/](./test_ament_nodl/), [test_nodl_generators/](./test_nodl_generators/), [test_nodl_generators_ament_python/](./test_nodl_generators_ament_python/) and [test_nodl_generators_downstream/](./test_nodl_generators_downstream/): Integration tests for the CMake macros and the code generators
- [tools/](./tools/): Scripts supporting development and build workflows

## Developing

See [RELEASING.md](./RELEASING.md) for versioning and tag releases.

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

## ROS Distribution Status

| Distro | Dev | Doc | Ubuntu Bin |
|--------|-----|-----|-----------|
| Humble | [![Hdev](https://build.ros2.org/job/Hdev__nodl__ubuntu_jammy_amd64/badge/icon?subject=Hdev)](https://build.ros2.org/job/Hdev__nodl__ubuntu_jammy_amd64/) | [![Hdoc](https://build.ros2.org/job/Hdoc__nodl__ubuntu_jammy_amd64/badge/icon?subject=Hdoc)](https://build.ros2.org/job/Hdoc__nodl__ubuntu_jammy_amd64/) | [![Hbin](https://build.ros2.org/job/Hbin_uJ64__nodl__ubuntu_jammy_amd64__binary/badge/icon?subject=Hbin)](https://build.ros2.org/job/Hbin_uJ64__nodl__ubuntu_jammy_amd64__binary/) |
| Jazzy | [![Jdev](https://build.ros2.org/job/Jdev__nodl__ubuntu_noble_amd64/badge/icon?subject=Jdev)](https://build.ros2.org/job/Jdev__nodl__ubuntu_noble_amd64/) | [![Jdoc](https://build.ros2.org/job/Jdoc__nodl__ubuntu_noble_amd64/badge/icon?subject=Jdoc)](https://build.ros2.org/job/Jdoc__nodl__ubuntu_noble_amd64/) | [![Jbin](https://build.ros2.org/job/Jbin_uN64__nodl__ubuntu_noble_amd64__binary/badge/icon?subject=Jbin)](https://build.ros2.org/job/Jbin_uN64__nodl__ubuntu_noble_amd64__binary/) |
| Lyrical | [![Ldev](https://build.ros2.org/job/Ldev__nodl__ubuntu_resolute_amd64/badge/icon?subject=Ldev)](https://build.ros2.org/job/Ldev__nodl__ubuntu_resolute_amd64/) | [![Ldoc](https://build.ros2.org/job/Ldoc__nodl__ubuntu_resolute_amd64/badge/icon?subject=Ldoc)](https://build.ros2.org/job/Ldoc__nodl__ubuntu_resolute_amd64/) | [![Lbin](https://build.ros2.org/job/Lbin_uR64__nodl__ubuntu_resolute_amd64__binary/badge/icon?subject=Lbin)](https://build.ros2.org/job/Lbin_uR64__nodl__ubuntu_resolute_amd64__binary/) |
| Rolling | [![Rdev](https://build.ros2.org/job/Rdev__nodl__ubuntu_resolute_amd64/badge/icon?subject=Rdev)](https://build.ros2.org/job/Rdev__nodl__ubuntu_resolute_amd64/) | [![Rdoc](https://build.ros2.org/job/Rdoc__nodl__ubuntu_resolute_amd64/badge/icon?subject=Rdoc)](https://build.ros2.org/job/Rdoc__nodl__ubuntu_resolute_amd64/) | [![Rbin](https://build.ros2.org/job/Rbin_uR64__nodl__ubuntu_resolute_amd64__binary/badge/icon?subject=Rbin)](https://build.ros2.org/job/Rbin_uR64__nodl__ubuntu_resolute_amd64__binary/) |

### Unsupported Distributions

These ROS distributions will receive no future release updates or code compatibility support.

| Distro | Date Support Ended | Reason |
| ------ | ------------------ | ------ |
| Kilted Kaiju | October 5, 2026 | Distro EOL in November |
