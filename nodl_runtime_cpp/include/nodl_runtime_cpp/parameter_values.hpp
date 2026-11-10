// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <algorithm>
#include <cmath>
#include <iterator>
#include <type_traits>
#include <utility>

namespace nodl_runtime_cpp
{

namespace detail
{

template <typename T, typename = void>
struct IsRange : std::false_type
{};

template <typename T>
struct IsRange<
  T,
  std::void_t<decltype(std::begin(std::declval<const T &>())), decltype(std::end(std::declval<const T &>()))>>
: std::true_type
{};

}  // namespace detail

/// Returns whether two parameter values are equal, treating NaN as equal to NaN.
/// Elements of arrays and vectors compare the same way, so an array of doubles holding NaN equals itself.
template <typename T>
bool values_equal(const T & first, const T & second)
{
  if constexpr (std::is_floating_point_v<T>) {
    return first == second || (std::isnan(first) && std::isnan(second));
  } else if constexpr (detail::IsRange<T>::value) {
    return std::distance(std::begin(first), std::end(first)) == std::distance(std::begin(second), std::end(second)) &&
           std::equal(std::begin(first), std::end(first), std::begin(second), [](const auto & a, const auto & b) {
             return values_equal(a, b);
           });
  } else {
    return first == second;
  }
}

}  // namespace nodl_runtime_cpp
