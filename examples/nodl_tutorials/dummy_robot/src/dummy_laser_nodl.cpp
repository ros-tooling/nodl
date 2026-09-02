// SPDX-FileCopyrightText: 2017 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <memory>

// Generated from dummy_laser_codegen.nodl.yaml.
#include "dummy_laser.hpp"  // NOLINT(build/include_subdir)
#include "nodl_tutorial_dummy_robot/laser_scan.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"

class DummyLaser : public DummyLaserBase
{
public:
  DummyLaser()
  : msg_(nodl_tutorial_dummy_robot::make_laser_scan())
  {}

  void publish_next_scan()
  {
    nodl_tutorial_dummy_robot::update_laser_scan(msg_, get_clock()->now(), counter_);
    pub_scan_->publish(msg_);
  }

private:
  sensor_msgs::msg::LaserScan msg_;
  double counter_{0.0};
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<DummyLaser>();
  rclcpp::WallRate loop_rate(30);
  rclcpp::executors::SingleThreadedExecutor executor;
  executor.add_node(node);
  while (rclcpp::ok()) {
    node->publish_next_scan();
    executor.spin_some();
    loop_rate.sleep();
  }
  rclcpp::shutdown();
  return 0;
}
