// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>

#include "cpp_minimal_static_node_base.hpp"  // NOLINT(build/include_subdir)

class StaticPluginNode : public CppMinimalStaticNodeBase
{};

std::shared_ptr<rclcpp::Node> make_static_plugin_node()
{
  return std::make_shared<StaticPluginNode>();
}
