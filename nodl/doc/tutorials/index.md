# Tutorials

These tutorials use real ROS 2 projects to show how NoDL can describe, specify, generate, and conform ROS interfaces.

```{toctree}
:hidden:

basics
dummy-robot
nav2-migration
nav2-server-composition
```

## Available tutorials

- [**ROS 2 basics: one NoDL contract, multiple bindings**](basics.md)
  Specify one talker contract, generate C++ or Python bindings, then catch QoS drift.

- [**Test the Dummy robot for conformance**](dummy-robot.md)
  Compare an unmodified ROS 2 node with contracts that change its topic, type, or reliability.

- [**Nav2: migrate one client, keep the system**](nav2-migration.md)
  Replace one navigation client while every Nav2 server remains conventional and unchanged.

- [**Nav2: compose a server contract**](nav2-server-composition.md)
  Combine framework-owned lifecycle interfaces with endpoints owned by the Controller Server.
