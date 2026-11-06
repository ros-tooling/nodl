# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The greeter, spun with a multi-threaded executor."""

import sys

from greeter import Greeter
from rclpy.executors import MultiThreadedExecutor

from nodl_runtime_py import run_node


def main():
    return run_node(Greeter, executor_class=MultiThreadedExecutor)


if __name__ == '__main__':
    sys.exit(main())
