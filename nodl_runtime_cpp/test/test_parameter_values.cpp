// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <array>
#include <limits>
#include <string>
#include <vector>

#include "nodl_runtime_cpp/parameter_values.hpp"

namespace
{

using nodl_runtime_cpp::values_equal;

const double NAN_VALUE = std::numeric_limits<double>::quiet_NaN();

}  // namespace

TEST(ParameterValues, ScalarsCompareByValue)
{
  EXPECT_TRUE(values_equal(1.5, 1.5));
  EXPECT_FALSE(values_equal(1.5, 2.5));
  EXPECT_TRUE(values_equal(std::string("a"), std::string("a")));
  EXPECT_FALSE(values_equal(true, false));
}

TEST(ParameterValues, NanEqualsNanButNotANumber)
{
  EXPECT_TRUE(values_equal(NAN_VALUE, NAN_VALUE));
  EXPECT_FALSE(values_equal(NAN_VALUE, 1.0));
  EXPECT_FALSE(values_equal(1.0, NAN_VALUE));
}

TEST(ParameterValues, RangesCompareElementwiseWithNan)
{
  EXPECT_TRUE(values_equal(std::vector<double>{1.0, NAN_VALUE}, std::vector<double>{1.0, NAN_VALUE}));
  EXPECT_FALSE(values_equal(std::vector<double>{1.0, NAN_VALUE}, std::vector<double>{NAN_VALUE, 1.0}));
  EXPECT_FALSE(values_equal(std::vector<double>{1.0}, std::vector<double>{1.0, 1.0}));
  EXPECT_TRUE(values_equal(std::array<double, 2>{NAN_VALUE, 2.0}, std::array<double, 2>{NAN_VALUE, 2.0}));
  EXPECT_TRUE(values_equal(std::vector<std::string>{"a", "b"}, std::vector<std::string>{"a", "b"}));
  EXPECT_FALSE(values_equal(std::vector<std::string>{"a"}, std::vector<std::string>{"b"}));
}
