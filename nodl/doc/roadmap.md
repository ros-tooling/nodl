# NoDL v2 Roadmap

These key features are targeted by the [NoDL v2 project](https://github.com/ros-tooling/nodl/milestone/1).

1. Core schema & validation
1. "Register": Allow packages to expose their NoDL documents to the ament index for other packages to consume.
1. "Compose": Allow for proper handling of code components that extend a node's interface beyond the node author's definitions, such as the base `rclcpp::Node` class or a TF Broadcaster,
1. "Describe": Observe a running instance of a node, and produce a NoDL document matching it as completely as possible.
1. "Generate": Taking a NoDL document as input, produce a node with that interface, allowing the author to skip the boilerplate and write only the business logic. Targeting C++ (`rclcpp`), Python (`rclpy`), and a stretch goal for Rust (`rclrs`).
1. "Document": Produce `rosdoc2`-compatible documentation pages from NoDL documents, to standardize the ROS node interface documentation story, which so far is ad-hoc and often entirely missing.
1. "Test": Guarantee schema conformance of NoDL-described nodes.
1. "Analyze": Enable pre-run analysis of NoDL-described ROS applications, checking connectivity and compatibility of communication endpoints without having to start a node process.
