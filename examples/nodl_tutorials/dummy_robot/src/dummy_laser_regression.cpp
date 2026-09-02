// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <string>

#include "nodl_tutorial_dummy_robot/laser_scan.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "sensor_msgs/msg/point_cloud.hpp"

struct RegressionOptions
{
  std::string topic{"scan"};
  std::string type{"laser_scan"};
  std::string reliability{"reliable"};
  std::string durability{"volatile"};
  std::string history{"keep_last"};
  std::size_t depth{10};
};

RegressionOptions parse_options(const int argc, char ** argv)
{
  RegressionOptions options;
  if (argc > 1) {
    options.topic = argv[1];
  }
  if (argc > 2) {
    options.type = argv[2];
  }
  if (argc > 3) {
    options.reliability = argv[3];
  }
  if (argc > 4) {
    options.durability = argv[4];
  }
  if (argc > 5) {
    options.history = argv[5];
  }
  if (argc > 6) {
    options.depth = std::stoul(argv[6]);
  }
  return options;
}

rclcpp::QoS make_qos(const RegressionOptions & options)
{
  rclcpp::QoS qos(options.depth);
  if (options.history == "keep_all") {
    qos.keep_all();
  } else if (options.history == "keep_last") {
    qos.keep_last(options.depth);
  } else {
    throw std::invalid_argument("history must be keep_last or keep_all");
  }

  if (options.reliability == "best_effort") {
    qos.best_effort();
  } else if (options.reliability == "reliable") {
    qos.reliable();
  } else {
    throw std::invalid_argument("reliability must be reliable or best_effort");
  }

  if (options.durability == "transient_local") {
    qos.transient_local();
  } else if (options.durability == "volatile") {
    qos.durability_volatile();
  } else {
    throw std::invalid_argument("durability must be volatile or transient_local");
  }
  return qos;
}

class RegressionLaser : public rclcpp::Node
{
public:
  explicit RegressionLaser(const RegressionOptions & options)
  : Node("dummy_laser")
  , msg_(nodl_tutorial_dummy_robot::make_laser_scan())
  {
    const auto qos = make_qos(options);
    if (options.type == "point_cloud") {
      point_cloud_pub_ = create_publisher<sensor_msgs::msg::PointCloud>(options.topic, qos);
    } else if (options.type == "laser_scan") {
      laser_scan_pub_ = create_publisher<sensor_msgs::msg::LaserScan>(options.topic, qos);
    } else {
      throw std::invalid_argument("type must be laser_scan or point_cloud");
    }
  }

  void publish_next_scan()
  {
    const auto stamp = get_clock()->now();
    if (laser_scan_pub_) {
      nodl_tutorial_dummy_robot::update_laser_scan(msg_, stamp, counter_);
      laser_scan_pub_->publish(msg_);
    } else {
      sensor_msgs::msg::PointCloud msg;
      msg.header.frame_id = "single_rrbot_hokuyo_link";
      msg.header.stamp = stamp;
      point_cloud_pub_->publish(msg);
    }
  }

private:
  rclcpp::Publisher<sensor_msgs::msg::LaserScan>::SharedPtr laser_scan_pub_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud>::SharedPtr point_cloud_pub_;
  sensor_msgs::msg::LaserScan msg_;
  double counter_{0.0};
};

int main(int argc, char ** argv)
{
  const auto options = parse_options(argc, argv);
  rclcpp::init(argc, argv);
  auto node = std::make_shared<RegressionLaser>(options);
  rclcpp::WallRate loop_rate(30);
  while (rclcpp::ok()) {
    node->publish_next_scan();
    rclcpp::spin_some(node);
    loop_rate.sleep();
  }
  rclcpp::shutdown();
  return 0;
}
