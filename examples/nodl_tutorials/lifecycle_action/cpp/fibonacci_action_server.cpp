// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <atomic>
#include <chrono>
#include <functional>
#include <memory>
#include <thread>

#include "example_interfaces/action/fibonacci.hpp"
#include "nodl_tutorial_lifecycle_action_cpp/fibonacci_action_server_cpp_base.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "rclcpp_lifecycle/node_interfaces/lifecycle_node_interface.hpp"

using std::chrono_literals::operator""ms;

class FibonacciActionServer : public FibonacciActionServerCppBase
{
  using Fibonacci = example_interfaces::action::Fibonacci;
  using GoalHandle = rclcpp_action::ServerGoalHandle<Fibonacci>;
  using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

protected:
  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) override
  {
    const auto result = FibonacciActionServerCppBase::on_activate(previous_state);
    active_.store(result == CallbackReturn::SUCCESS);
    return result;
  }

  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) override
  {
    active_.store(false);
    return FibonacciActionServerCppBase::on_deactivate(previous_state);
  }

  rclcpp_action::GoalResponse on_fibonacci_goal(
    const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const Fibonacci::Goal> goal) override
  {
    (void)uuid;
    RCLCPP_INFO(get_logger(), "Received goal request with order %d", goal->order);
    if (!active_.load() || goal->order < 0 || goal->order > 46) {
      return rclcpp_action::GoalResponse::REJECT;
    }
    return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
  }

  rclcpp_action::CancelResponse on_fibonacci_cancel(std::shared_ptr<GoalHandle> goal_handle) override
  {
    (void)goal_handle;
    RCLCPP_INFO(get_logger(), "Received request to cancel goal");
    return rclcpp_action::CancelResponse::ACCEPT;
  }

  void on_fibonacci_accepted(std::shared_ptr<GoalHandle> goal_handle) override
  {
    std::thread{std::bind(&FibonacciActionServer::execute, this, std::placeholders::_1), goal_handle}.detach();
  }

private:
  void execute(const std::shared_ptr<GoalHandle> goal_handle)
  {
    const auto goal = goal_handle->get_goal();
    auto feedback = std::make_shared<Fibonacci::Feedback>();
    feedback->sequence = {0, 1};
    auto result = std::make_shared<Fibonacci::Result>();

    for (int i = 1; i < goal->order && rclcpp::ok(); ++i) {
      if (goal_handle->is_canceling()) {
        result->sequence = feedback->sequence;
        goal_handle->canceled(result);
        return;
      }
      feedback->sequence.push_back(
        feedback->sequence[static_cast<std::size_t>(i)] + feedback->sequence[static_cast<std::size_t>(i - 1)]);
      goal_handle->publish_feedback(feedback);
      std::this_thread::sleep_for(100ms);
    }

    if (rclcpp::ok()) {
      result->sequence = feedback->sequence;
      goal_handle->succeed(result);
    }
  }

  std::atomic_bool active_{false};
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<FibonacciActionServer>()->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
