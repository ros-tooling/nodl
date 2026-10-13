# Tutorials

These tutorials use real ROS 2 projects to show how NoDL can describe, specify, generate, and conform ROS interfaces.

```{toctree}
:hidden:

basics
dummy-robot
lifecycle-action-server
```

## Available tutorials

- [**ROS 2 basics: one NoDL contract, multiple bindings**](basics.md)
  Specify one talker contract, generate C++ or Python bindings, then catch QoS drift.

- [**Test the Dummy robot for conformance**](dummy-robot.md)
  Compare an unmodified ROS 2 node with contracts that change its topic, type, or reliability.

- [**Tutorial 4: build a lifecycle action server in C++ and Python**](lifecycle-action-server.md)
  Generate two lifecycle bases from one public Fibonacci action contract, then test application-owned gating.
