// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <rcl/arguments.h>
#include <rcl/error_handling.h>
#include <rcl_yaml_param_parser/parser.h>

#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

#include <rcl_interfaces/msg/parameter.hpp>
#include <rclcpp/parameter_map.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>

namespace
{
struct Arguments
{
  rcl_arguments_t value = rcl_get_zero_initialized_arguments();
  bool initialized = false;

  ~Arguments()
  {
    if (initialized && rcl_arguments_fini(&value) != RCL_RET_OK) {
      rcl_reset_error();
    }
  }
};
}  // namespace

// Resolve explicit ROS configuration without initializing a context or joining the graph.
// Frame each serialized Parameter message with its byte length and a newline.
// ROS serialization preserves strings and floating point values without text conversion.
int main(int argc, char ** argv)
{
  try {
    if (argc < 2) {
      throw std::invalid_argument("usage: resolve_parameters NODE_FQN --ros-args [parameter arguments]");
    }
    Arguments arguments;
    if (
      RCL_RET_OK !=
      rcl_parse_arguments(argc - 2, const_cast<const char **>(argv + 2), rcl_get_default_allocator(), &arguments.value))
    {
      const std::string error = rcl_get_error_string().str;
      rcl_reset_error();
      throw std::invalid_argument(error);
    }
    arguments.initialized = true;
    if (
      rcl_arguments_get_count_unparsed(&arguments.value) != 0 ||
      rcl_arguments_get_count_unparsed_ros(&arguments.value) != 0)
    {
      throw std::invalid_argument("unrecognized ROS configuration argument");
    }
    rcl_params_t * raw = nullptr;
    if (RCL_RET_OK != rcl_arguments_get_param_overrides(&arguments.value, &raw)) {
      throw std::runtime_error(rcl_get_error_string().str);
    }
    const std::unique_ptr<rcl_params_t, decltype(&rcl_yaml_node_struct_fini)> parameters(
      raw, rcl_yaml_node_struct_fini);
    if (parameters) {
      const auto resolved = rclcpp::parameter_map_from(parameters.get(), argv[1]);
      const auto target = resolved.find(argv[1]);
      if (target != resolved.end()) {
        rclcpp::Serialization<rcl_interfaces::msg::Parameter> serializer;
        for (const auto & parameter : target->second) {
          const auto message = parameter.to_parameter_msg();
          rclcpp::SerializedMessage serialized;
          serializer.serialize_message(&message, &serialized);
          const auto & buffer = serialized.get_rcl_serialized_message();
          std::cout << buffer.buffer_length << '\n';
          std::cout.write(
            reinterpret_cast<const char *>(buffer.buffer), static_cast<std::streamsize>(buffer.buffer_length));
        }
      }
    }
    return 0;
  } catch (const std::exception & error) {
    std::cerr << "resolve_parameters: " << error.what() << '\n';
    return 1;
  }
}
