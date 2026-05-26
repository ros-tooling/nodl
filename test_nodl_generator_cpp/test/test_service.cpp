#include <chrono>
#include <memory>

#include <gtest/gtest.h>
#include <rclcpp/rclcpp.hpp>
#include <example_interfaces/srv/add_two_ints.hpp>

#include "service_node_derived.hpp"

using namespace std::chrono_literals;
using AddTwoInts = example_interfaces::srv::AddTwoInts;

class ServiceRoundTrip : public ::testing::Test
{
protected:
  void SetUp() override { rclcpp::init(0, nullptr); }
  void TearDown() override { rclcpp::shutdown(); }
};

// Server side: harness client → derived node's generated server on /add.
TEST_F(ServiceRoundTrip, GeneratedServerHandlesRequest)
{
  auto node = std::make_shared<ServiceNode>();
  auto harness = std::make_shared<rclcpp::Node>("test_harness_srv");
  auto client = harness->create_client<AddTwoInts>("/add");

  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(node);
  exec.add_node(harness);

  const auto wait_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < wait_deadline && !client->service_is_ready()) {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_TRUE(client->service_is_ready()) << "derived node didn't advertise /add";

  auto req = std::make_shared<AddTwoInts::Request>();
  req->a = 3;
  req->b = 4;
  auto future = client->async_send_request(req);

  const auto resp_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < resp_deadline &&
         future.wait_for(0s) != std::future_status::ready)
  {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_EQ(future.wait_for(0s), std::future_status::ready) << "no response from /add";

  EXPECT_EQ(node->add_call_count, 1);
  EXPECT_EQ(future.get()->sum, 7);
}

// Client side: derived node's generated client → harness server on /delegate_add.
TEST_F(ServiceRoundTrip, GeneratedClientCallsServer)
{
  auto node = std::make_shared<ServiceNode>();
  auto harness = std::make_shared<rclcpp::Node>("test_harness_srv_client");

  int server_call_count = 0;
  auto server = harness->create_service<AddTwoInts>(
    "/delegate_add",
    [&server_call_count](
      AddTwoInts::Request::SharedPtr req,
      AddTwoInts::Response::SharedPtr res)
    {
      ++server_call_count;
      res->sum = req->a * 10 + req->b;  // distinctive op so we know which side ran.
    });

  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(node);
  exec.add_node(harness);

  auto cli = node->delegate_client();
  ASSERT_NE(cli, nullptr) << "generated client member not constructed";

  const auto wait_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < wait_deadline && !cli->service_is_ready()) {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_TRUE(cli->service_is_ready()) << "generated client didn't see /delegate_add";

  auto req = std::make_shared<AddTwoInts::Request>();
  req->a = 5;
  req->b = 2;
  auto future = cli->async_send_request(req);

  const auto resp_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < resp_deadline &&
         future.wait_for(0s) != std::future_status::ready)
  {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_EQ(future.wait_for(0s), std::future_status::ready);

  EXPECT_EQ(server_call_count, 1);
  EXPECT_EQ(future.get()->sum, 52);
}
