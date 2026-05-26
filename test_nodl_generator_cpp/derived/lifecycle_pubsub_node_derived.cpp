#include "lifecycle_pubsub_node_derived.hpp"

void LifecyclePubsubNode::on_lc_echo_in(std_msgs::msg::String::ConstSharedPtr msg)
{
  last_received = msg->data;
  ++receive_count;

  std_msgs::msg::String out;
  out.data = "lc-echo: " + msg->data;
  pub_lc_echo_out_->publish(out);
}
