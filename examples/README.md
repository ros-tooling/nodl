# NoDL tutorial examples

This directory contains executable support for the NoDL tutorials.

The first pass deliberately uses only capabilities available on NoDL `main`:

- schema validation;
- ament registration;
- live observation as `rosgraph_msgs/Node`;
- manual curation of a NoDL document.

It does not provide tutorial-local implementations of generation, composition, semantic diff, or conformance.

## Reproduce the upstream workspace

The locked manifest pins the `ros2/demos` revision inspected by the tutorials.

From the NoDL repository root:

```bash
./examples/bootstrap.bash /tmp/nodl-tutorial-ws
```

The script imports `ros2/demos`, links the current NoDL checkout into the workspace, installs ROS dependencies, and
builds the selected packages. Use a new or empty destination.

The initial lock was reviewed on 2026-08-04:

- NoDL: `427369df8af2e172797e088f7ec6d2bbe812b277`
- `ros2/demos`: `f8d20abaec2be76c7062b2a0242ae6f82e2857b8`

The NoDL revision above records the review baseline. The linked checkout can contain the tutorial changes under review.

## Prototype document ownership

`nodl_tutorial_verification/nodl/` holds the curated first-pass documents. These files are executable documentation
fixtures, not yet canonical upstream declarations. A later `ros2/demos` PR may move the accepted documents beside the
node sources.

## Current manual rehearsal

After sourcing the built workspace, follow:

- [ROS 2 basics](../nodl/doc/tutorials/basics.md)
- [Dummy robot](../nodl/doc/tutorials/dummy-robot.md)

Raw Describe output is not valid NoDL on current `main`. Inspect it as an observation record, then validate the curated
documents separately.
