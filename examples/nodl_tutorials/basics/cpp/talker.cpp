// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include "talker.hpp"  // NOLINT(build/include_subdir)

#include <chrono>
#include <cstddef>
#include <memory>
#include <string>

#include "example_interfaces/msg/string.hpp"
#include "rclcpp/rclcpp.hpp"

using std::chrono_literals::operator""ms;

class Talker : public TalkerBase
{
public:
  Talker()
  : TalkerBase()
  {
    timer_ = create_wall_timer(500ms, [this]() { on_timer(); });
  }

private:
  void on_timer()
  {
    example_interfaces::msg::String message;
    message.data = "Hello World: " + std::to_string(count_++);
    pub_chatter_->publish(message);
  }

  std::size_t count_{0};
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Talker>());
  rclcpp::shutdown();
  return 0;
}
