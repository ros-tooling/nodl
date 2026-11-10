// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

// SPDX-FileCopyrightText: 2026 Polymath Robotics, Inc.
// SPDX-License-Identifier: Apache-2.0
//
// Copied from ros-tooling/graph-monitor (rosgraph_monitor/include/rosgraph_monitor/mutex_protected.hpp).
#pragma once

#include <mutex>
#include <utility>

namespace nodl_runtime_cpp
{

/// Holds a value that can only be reached while holding its mutex.
/// @tparam T Type of the protected value
/// @tparam Mutex Type of the mutex
template <typename T, typename Mutex = std::mutex>
class MutexProtected
{
public:
  /// RAII guard that holds the lock for its lifetime.
  /// @tparam Value `T` for mutable access, `const T` for read-only access
  template <typename Value>
  class GuardT
  {
  public:
    GuardT(Value & value, Mutex & mtx)
    : lock_(mtx)
    , value_(value)
    {}

    Value * operator->() const
    {
      return &value_;
    }

    Value & operator*() const
    {
      return value_;
    }

    GuardT(const GuardT &) = delete;
    GuardT & operator=(const GuardT &) = delete;

    GuardT(GuardT &&) = default;
    GuardT & operator=(GuardT &&) = default;

  private:
    std::unique_lock<Mutex> lock_;
    Value & value_;
  };

  using Guard = GuardT<T>;
  using ConstGuard = GuardT<const T>;

  MutexProtected() = delete;

  /// Copies the initial value.
  explicit MutexProtected(const T & initial_value)
  : value_(initial_value)
  {}

  /// Constructs the value in place from @p args.
  template <typename... Args>
  explicit MutexProtected(Args &&... args)
  : value_(std::forward<Args>(args)...)
  {}

  /// Blocks until the lock is free, then returns a guard with mutable access.
  Guard lock()
  {
    return Guard(value_, mutex_);
  }

  /// Blocks until the lock is free, then returns a guard with read-only access.
  ConstGuard lock() const
  {
    return ConstGuard(value_, mutex_);
  }

private:
  T value_;
  mutable Mutex mutex_;
};

}  // namespace nodl_runtime_cpp
