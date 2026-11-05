# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from echo_robot_py.echo_node import EchoNode
from echo_robot_py.generated.echo_node_base import EchoNodeBase


def test_echo_node_extends_the_generated_base():
    assert issubclass(EchoNode, EchoNodeBase)
