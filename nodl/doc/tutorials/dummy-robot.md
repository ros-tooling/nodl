# Dummy robot: preserve a visible system

`dummy_robot` combines a map server, fake joint states, fake laser data, `robot_state_publisher`, TF, launch, and RViz.
The worked migration subject is `dummy_laser`, but the success condition is system-level: the robot and laser scan
remain visible.

```text
dummy_laser ── /scan (frame_id) ──> RViz
robot_state_publisher ── /tf ─────> RViz
```

The reviewed source is
[`dummy_sensors/src/dummy_laser.cpp`](https://github.com/ros2/demos/blob/f8d20abaec2be76c7062b2a0242ae6f82e2857b8/dummy_robot/dummy_sensors/src/dummy_laser.cpp).

> **Launch → Describe → Curate → Generate → Regress → Recover**

:::{note}
**Capability status:** Launch, describe, and validate work on NoDL `main`. Generate, semantic diff, and running-node
conformance below are a draft workflow; they are not implemented on `main`.
:::

NoDL owns ROS interface declarations. It does not own scan calculation, timestamps, loop rate, real-time guarantees,
or TF lookup behavior.

## 1. Launch the existing robot

Build and launch the complete upstream robot:

```bash
colcon build --packages-select dummy_map_server dummy_sensors dummy_robot_bringup
ros2 launch dummy_robot_bringup dummy_robot_bringup_launch.py
```

RViz should show the robot and its changing laser scan. This is the baseline that every later step must preserve.

## 2. Describe the laser interface

In another terminal, recover the interface of the existing `/dummy_laser` node:

```bash
ros2 nodl describe /dummy_laser \
  -o /tmp/dummy_laser.observed.nodl.yaml
```

`describe` already emits schema-valid NoDL on current `main`. It operates on one node, so it does not claim to
describe the complete robot. There is no `describe-system` command in this workflow.

Verify the behavior and frame relationship separately:

```bash
ros2 topic echo /scan --once
ros2 run tf2_ros tf2_echo world single_rrbot_hokuyo_link
```

These commands answer different questions:

| Claim | Check |
|---|---|
| `/dummy_laser` publishes the declared endpoint | NoDL description and, later, conformance |
| Scan messages arrive | `ros2 topic echo` |
| The laser frame connects to the robot frame tree | `tf2_echo` |
| RViz can render the result | The visible system test |

Declaring `/tf` or `/tf_static` transport endpoints would not prove the required frame path.

## 3. Curate the recovered contract

Review the discovered type and QoS, change resolved runtime names back to deliberate source-level names where useful,
and add documentation. The curated contract used by this tutorial is:

```{literalinclude} ../../../examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
:language: yaml
```

Validate the document after those edits:

```bash
ros2 nodl validate examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

## 4. Generate the interface without replacing behavior

:::{warning}
**Draft workflow — not yet implemented.** The `generate` and `conform` commands in the remaining steps show the
intended product experience. They are not available on NoDL `main`.
:::

Generate a C++ interface binding from the curated document and combine it with the existing scan behavior:

```bash
ros2 nodl generate \
  examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml \
  --language cpp --output generated/dummy_laser
colcon build --packages-select nodl_dummy_robot_demo
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py interface:=nodl
```

### Before and after: replace wiring, preserve behavior

The migration does not replace the fake-laser algorithm. It moves the publisher declaration into the generated base
and reconnects the existing 30 Hz loop to that publisher. These abbreviated extracts keep the relevant lines from
the [upstream implementation](https://github.com/ros2/demos/blob/f8d20abaec2be76c7062b2a0242ae6f82e2857b8/dummy_robot/dummy_sensors/src/dummy_laser.cpp).
Follow the comments: **Interface** moves behind the generated base; **Behavior** remains ordinary C++.

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
    // [Interface] DummyLaserBase has already created pub_scan_ with
    // the contract's topic name, LaserScan type, and QoS.

    // [Behavior] Keep the same frame, angle, range, and timing setup.
  }

  void publish_next_scan()
  {
    // [Behavior] This is the existing fake-laser calculation.
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

The NoDL document now owns the `/scan` name, `LaserScan` type, and QoS. The handwritten C++ still owns scan values,
timestamps, the 30 Hz loop, and when publication occurs. The generated API above is part of the draft workflow.

Confirm that the generated interface matches the same contract:

```bash
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

The expected result is a conforming node while RViz continues to show the robot and scan.

## 5. Regress one interface property

The implementation fixture provides one launch argument per deliberate regression. Run only one at a time, leaving
the expected NoDL contract unchanged:

| Regression | Expected semantic result | Visible result |
|---|---|---|
| Topic name | Missing `/scan`; extra `/scan_regressed` | RViz loses the scan |
| Message type | Type mismatch on `/scan` | RViz rejects the data |
| Reliability | `RELIABLE` versus `BEST_EFFORT` | Scan may still appear |
| Durability | `VOLATILE` versus `TRANSIENT_LOCAL` | Usually unchanged |
| History | `KEEP_LAST` versus `KEEP_ALL` | Usually unchanged |
| Depth | `10` versus `1` | Usually unchanged |

Choose one regression below. Each tab changes the running implementation while leaving
`dummy_laser.nodl.yaml` unchanged.

::::{tabs}
:::{tab} Topic

Rename the publisher so the expected endpoint disappears:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_topic:=scan_regressed
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

Expected diff:

```text
[missing] publishers '/scan': expected sensor_msgs/msg/LaserScan
[extra] publishers '/scan_regressed': observed sensor_msgs/msg/LaserScan
```

RViz loses the laser scan because nothing publishes its configured `/scan` topic.
:::

:::{tab} Type

Keep `/scan`, but publish a different message type:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_type:=point_cloud
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

Expected diff:

```text
[mismatch] publishers '/scan'.type:
  expected sensor_msgs/msg/LaserScan
  observed sensor_msgs/msg/PointCloud
```

RViz cannot use the data as a `LaserScan`, even though the topic name still matches.
:::

:::{tab} Reliability

Change only the publisher reliability policy:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_reliability:=best_effort
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

Expected diff:

```text
[mismatch] publishers '/scan'.qos.reliability:
  expected RELIABLE
  observed BEST_EFFORT
```

The scan may remain visible. Conformance detects contract drift even when the system still appears to work.
:::

:::{tab} Durability

Change only the publisher durability policy:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_durability:=transient_local
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

Expected diff:

```text
[mismatch] publishers '/scan'.qos.durability:
  expected VOLATILE
  observed TRANSIENT_LOCAL
```

RViz usually looks unchanged, but the publisher can now retain data for compatible transient-local late subscribers.
:::

:::{tab} History

Change only the publisher history policy:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_history:=keep_all
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

Expected diff:

```text
[mismatch] publishers '/scan'.qos.history:
  expected KEEP_LAST
  observed KEEP_ALL
```

The live display usually looks unchanged; the publisher's queueing contract has changed.
:::

:::{tab} Depth

Keep `KEEP_LAST`, but reduce its queue depth:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py \
  interface:=conventional scan_depth:=1
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

Expected diff:

```text
[mismatch] publishers '/scan'.qos.depth:
  expected 10
  observed 1
```

RViz usually looks unchanged, but the publisher retains fewer unsent samples.
:::
::::

:::{important}
**QoS test requirement:** the implementation PR must record a tested ROS distribution and RMW combination for each
QoS field above. If discovery cannot observe a field, conformance must report `unverifiable`; it must never infer a
pass or mismatch. A tutorial release may limit a regression to the tested combinations listed with that release.
:::

## 6. Recover the visible system

Restore the generated interface and run the same contract check again:

```bash
ros2 launch nodl_dummy_robot_demo dummy_robot.launch.py interface:=nodl
ros2 nodl conform /dummy_laser \
  --file examples/nodl_tutorial_verification/nodl/dummy_laser.nodl.yaml
```

The final result is not only a passing conformance report. The robot and laser scan must also be working in RViz.

This progression demonstrates discovery on an existing node, interface-only migration, semantic regression
detection, and recovery without treating NoDL as the owner of robot behavior.
