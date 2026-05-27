<!--
SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
SPDX-License-Identifier: Apache-2.0
-->

# NoDL

NoDL (Node Definition Language) is a schema-driven description of a ROS 2 node's public interface: parameters, publishers, subscriptions, services, and actions.

:::{note}
**Status: v2 development.** The schema and APIs are not yet stable. Expect breaking changes until v2 is announced for a ROS distribution.
:::

## Documentation

```{toctree}
:maxdepth: 2

concepts
schema
```

## Packages

- **`nodl_schema`** — the JSON Schema, validator, and Python data model.
- **`ros2nodl`** — `ros2 nodl <verb>` ros2cli plugin.
- **`ament_nodl`** — CMake macros for registering NoDL files with the ament index.

Per-package documentation will land here as each package's surface stabilizes.

## Source

Repository: <https://github.com/ros-tooling/nodl>
