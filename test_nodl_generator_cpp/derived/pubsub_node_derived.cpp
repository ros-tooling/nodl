#include "pubsub_node_derived.hpp"

void PubsubNode::on_echo_in(std_msgs::msg::String::ConstSharedPtr msg)
{
  last_received = msg->data;
  ++receive_count;

  std_msgs::msg::String out;
  out.data = "echo: " + msg->data;
  pub_echo_out_->publish(out);
}
