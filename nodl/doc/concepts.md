<!--
SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
SPDX-License-Identifier: Apache-2.0
-->

# Concepts

A NoDL document declares a ROS 2 node's public interface in YAML or JSON.
It is consumed at runtime by helpers that bind a node to its declared shape, at build time by code generators, and at documentation time to describe a node to its users.

## Node identity

A NoDL document does not declare its own name, package, or namespace.
Those come from the containing ROS package and the file's location within it.
The document describes interfaces, not identity.

## What can be described

- **Parameters** — typed, with optional default value, description, read-only flag, and validation rules.
- **Publishers and subscriptions** — by topic name, message type, and QoS profile.
- **Service servers and clients** — by service name and service type.
- **Action servers and clients** — by action name and action type.

See the [schema reference](schema.md) for the field-by-field detail.

## Composition

A node document may declare a `base` (one of `node` or `lifecycle_node`) and a list of `fragments` to compose its interface from reusable pieces.
At resolution time, the resolver loads the base, then each fragment in the order they are declared, then the main document; later layers win on duplicate names.

Fragments themselves are flat:
they cannot declare a `base` or their own `fragments`.
Nested composition is intentionally disallowed in v2.
If a real need surfaces, the constraint can be lifted without a schema change.

## Frontend independence

The schema is JSON Schema.
YAML and JSON files are accepted interchangeably as input; both deserialize to the same document model.
Tools should not assume a `.nodl.yaml` extension or a single frontend.

## Validation

NoDL files are validated both at build time (by the `ament_nodl` CMake macros, before install) and at runtime (by `nodl_schema.load_nodl` and `load_fragment`).
Authoring errors surface during the build of the package that owns the file, not at runtime, so a misconfigured node never ships.
