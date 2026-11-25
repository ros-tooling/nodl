---
name: migrate-lifecycle-node
description: Migrate a handwritten rclcpp_lifecycle or rclpy lifecycle node to a NoDL generated lifecycle node. Use when a node derives rclcpp_lifecycle::LifecycleNode or rclpy.lifecycle.LifecycleNode and should derive a generated base class that includes nodl://nodl_common_interfaces/lifecycle_node.
---

# Migrate a handwritten lifecycle node

The guide `nodl/doc/migrating-lifecycle-nodes.md` has the details and the tested before and after examples in `examples/nodl_tutorials/lifecycle_migration`.
Read it first, then do these steps for the node.

1. List the node's endpoints and parameters, and write a NoDL document that declares them with their QoS and includes `nodl://nodl_common_interfaces/lifecycle_node`.
1. Generate the base class with `nodl_generate_cpp` or `nodl_generate_py`, and declare `nodl_runtime_cpp` or `nodl_runtime_py` as a dependency.
1. Derive the generated base class, implement its abstract `on_<name>` callbacks, and delete the code that creates the declared endpoints and parameters.
1. Rename each `on_configure`, `on_activate`, `on_deactivate`, `on_cleanup`, `on_shutdown` and `on_error` to the matching `handle_*` hook, and delete the calls to the superclass transition callback.
1. Find code that relied on a subscription or service server existing while the node is unconfigured or inactive, and move it to run on activation or later.
1. Wrap each use of a service client or action client in a check of `get()`, which is null while the node is not active.
1. Create timers and threads in `handle_activate` and stop them in `handle_deactivate`, or hold them in a `Managed` member.
1. Leave action servers as they are, because the generated base does not manage them yet.
1. Add `nodl_add_conformance_test` for the node, which configures and activates it.

Verify with the package's tests and its conformance test: `colcon test --packages-select <package>` then `colcon test-result --verbose`.
