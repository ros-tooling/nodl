#include "service_node_derived.hpp"

void ServiceNode::on_add(
  example_interfaces::srv::AddTwoInts::Request::SharedPtr request,
  example_interfaces::srv::AddTwoInts::Response::SharedPtr response)
{
  ++add_call_count;
  response->sum = request->a + request->b;
}
