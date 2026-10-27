# Tutorials

These tutorials use real ROS 2 projects to show how NoDL can describe, specify, generate, and conform ROS interfaces.

```{toctree}
:hidden:

basics
dummy-robot
nav2-migration
```

## Available tutorials

- [**ROS 2 basics: one NoDL contract, multiple bindings**](basics.md)
  Specify one talker contract, generate C++ or Python bindings, then check conformance manually and with package tests.

- [**Test the Dummy robot for conformance**](dummy-robot.md)
  Compare an unmodified ROS 2 node with contracts that change its topic, type, or reliability.

- [**Nav2: migrate one client, keep the system**](nav2-migration.md)
  Replace one navigation client while every Nav2 server remains conventional and unchanged.
