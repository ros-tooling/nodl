# Dummy robot: preserve a visible system

`dummy_robot` combines a map server, fake joint states, fake laser data, `robot_state_publisher`, TF, launch, and
RViz. This tutorial migrates the `dummy_laser` interface while keeping the success criterion at system scale: the
robot and its laser scan remain visible.

```text
dummy_laser ── /scan (frame_id) ──> RViz
robot_state_publisher ── /tf ─────> RViz
```

The reviewed source is
[`dummy_sensors/src/dummy_laser.cpp`](https://github.com/ros2/demos/blob/f8d20abaec2be76c7062b2a0242ae6f82e2857b8/dummy_robot/dummy_sensors/src/dummy_laser.cpp).

> **Launch → Describe → Specify (NoDL) → Generate → Implement → Conform → Regress → Recover**

:::{note}
**Capability status:** Launch, describe, validate, and ament registration work on NoDL `main`. Generation, semantic
diff, and running-node conformance below show the intended workflow; they are not implemented on `main`.
:::

NoDL owns ROS interface declarations. It does not own scan calculation, timestamps, loop rate, real-time guarantees,
or TF lookup behavior.

## 1. Launch the existing robot

Build and launch the complete upstream robot:

```bash
colcon build --packages-select dummy_map_server dummy_sensors dummy_robot_bringup
ros2 launch dummy_robot_bringup dummy_robot_bringup_launch.py
```

RViz should show the robot and its changing laser scan. This is the baseline every later step must preserve.

## 2. Describe the laser interface

In another terminal, recover the interface of the existing `/dummy_laser` node:

```bash
ros2 nodl describe /dummy_laser \
  -o /tmp/dummy_laser.observed.nodl.yaml
```

`describe` operates on one node. It does not claim to describe the complete robot, and this workflow assumes no
`describe-system` command.

Check behavior and frame relationships separately:

```bash
ros2 topic echo /scan --once
ros2 run tf2_ros tf2_echo world single_rrbot_hokuyo_link
```

| Claim | Check |
|---|---|
| `/dummy_laser` publishes the declared endpoint | NoDL description and, later, conformance |
| Scan messages arrive | `ros2 topic echo` |
| The laser frame connects to the robot frame tree | `tf2_echo` |
| RViz can render the result | The visible system test |

Describing `/tf` or `/tf_static` transport endpoints would not prove the required frame path.

## 3. Specify the NoDL contract

Review the discovered type and QoS, change resolved runtime names back to deliberate source-level names where useful,
and add documentation. The edited contract is the source of truth for generated implementation, documentation, and
conformance.

```{literalinclude} ../../../examples/nodl_tutorials/dummy_robot/nodl/dummy_laser.nodl.yaml
:language: yaml
```

Validate the document after editing:

```bash
ros2 nodl validate examples/nodl_tutorials/dummy_robot/nodl/dummy_laser.nodl.yaml
```

## 4. Generate implementation without replacing behavior

:::{warning}
**Draft workflow, not yet implemented.** The implementation generator and `conform` command in the remaining steps
show the intended product experience. They are not available on NoDL `main`.
:::

Generate a C++ interface binding from the edited document and combine it with the existing scan behavior:

```bash
ros2 nodl generate \
  examples/nodl_tutorials/dummy_robot/nodl/dummy_laser.nodl.yaml \
  --language cpp --output generated/dummy_laser
colcon build --packages-select nodl_dummy_robot_demo
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py interface:=nodl
```

### Before and after: replace wiring, preserve behavior

The migration does not replace the fake-laser algorithm. It moves the publisher declaration into the generated base
and reconnects the existing 30 Hz loop to that publisher. **Interface** moves behind the generated base; **Behavior**
remains ordinary C++.

::::{tabs}
:::{tab} Before: conventional

```cpp
auto node = rclcpp::Node::make_shared("dummy_laser");

// [Interface] The handwritten node chooses the topic, type, and QoS.
auto laser_pub =
  node->create_publisher<sensor_msgs::msg::LaserScan>("scan", 10);

// [Behavior] The application owns its execution rate and scan data.
rclcpp::WallRate loop_rate(30);
sensor_msgs::msg::LaserScan msg;
// Existing frame, angle, range, and timing initialization.

while (rclcpp::ok()) {
  counter += 0.1;
  const auto distance =
    static_cast<float>(std::abs(amplitude * std::sin(counter)));
  for (auto & range : msg.ranges) {
    range = distance;
  }
  msg.header.stamp = clock->now();

  laser_pub->publish(msg);
  executor.spin_some();
  loop_rate.sleep();
}
```

:::

:::{tab} After: NoDL-forward

```cpp
// [Interface] Inherit the interface generated from dummy_laser.nodl.yaml.
class DummyLaser : public generated::DummyLaserBase
{
public:
  DummyLaser() : DummyLaserBase("dummy_laser")
  {
    // [Interface] DummyLaserBase created pub_scan_ from the contract.
    // [Behavior] Keep the existing frame, angle, range, and timing setup.
  }

  void publish_next_scan()
  {
    // [Behavior] Keep the existing fake-laser calculation.
    counter_ += 0.1;
    const auto distance =
      static_cast<float>(std::abs(amplitude_ * std::sin(counter_)));
    for (auto & range : msg_.ranges) {
      range = distance;
    }
    msg_.header.stamp = get_clock()->now();

    // [Interface] Publish through the generated contract endpoint.
    pub_scan_->publish(msg_);
  }

private:
  sensor_msgs::msg::LaserScan msg_;
  double counter_{0.0};
  int amplitude_{1};
};

// [Behavior] The executor and 30 Hz loop remain application code.
auto node = std::make_shared<DummyLaser>();
rclcpp::WallRate loop_rate(30);
rclcpp::executors::SingleThreadedExecutor executor;
executor.add_node(node);
while (rclcpp::ok()) {
  node->publish_next_scan();
  executor.spin_some();
  loop_rate.sleep();
}
```

:::
::::

The NoDL document owns the `/scan` name, `LaserScan` type, and QoS. The handwritten C++ still owns scan values,
timestamps, the 30 Hz loop, and when publication occurs.

## 5. Conform, then regress one interface property

First compare the generated implementation with the edited contract. The expected result is a conforming node while
RViz continues to show the robot and scan:

```bash
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorials/dummy_robot/nodl/dummy_laser.nodl.yaml
```

The implementation fixture provides one launch argument per deliberate regression. Run one at a time, leaving the
expected NoDL contract unchanged:

| Regression | Expected semantic result | Visible result |
|---|---|---|
| Topic name | Missing `/scan`; extra `/scan_regressed` | RViz loses the scan |
| Message type | Type mismatch on `/scan` | RViz rejects the data |
| Reliability | `RELIABLE` versus `BEST_EFFORT` | Scan may still appear |
| Durability | `VOLATILE` versus `TRANSIENT_LOCAL` | Usually unchanged |
| History | `KEEP_LAST` versus `KEEP_ALL` | Usually unchanged |
| Depth | `10` versus `1` | Usually unchanged |

::::{tabs}
:::{tab} Topic

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_topic:=scan_regressed
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorials/dummy_robot/nodl/dummy_laser.nodl.yaml
```

```text
[missing] publishers '/scan': expected sensor_msgs/msg/LaserScan
[extra] publishers '/scan_regressed': observed sensor_msgs/msg/LaserScan
```

RViz loses the laser scan because nothing publishes its configured `/scan` topic.
:::

:::{tab} Type

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_type:=point_cloud
```

```text
[mismatch] publishers '/scan'.type:
  expected sensor_msgs/msg/LaserScan
  observed sensor_msgs/msg/PointCloud
```

RViz cannot use the data as a `LaserScan`, even though the topic name still matches.
:::

:::{tab} QoS

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_reliability:=best_effort
```

```text
[mismatch] publishers '/scan'.qos.reliability:
  expected RELIABLE
  observed BEST_EFFORT
```

The scan may remain visible. Conformance detects contract drift even when the system still appears to work.
:::
::::

:::{important}
**QoS test requirement:** the implementation must record a tested ROS distribution and RMW combination for every QoS
field it reports. If discovery cannot observe a field, conformance must report `unverifiable`; it must never infer a
pass or mismatch.
:::

## 6. Recover the visible system

Restore the generated interface and run the same contract check again:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py interface:=nodl
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorials/dummy_robot/nodl/dummy_laser.nodl.yaml
```

The final result is not only a passing conformance report. The robot and laser scan must also be working in RViz.
