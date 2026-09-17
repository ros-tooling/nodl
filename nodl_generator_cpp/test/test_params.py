# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for generate_parameter_library input generation."""

import yaml

from nodl_generator_cpp.params import generate_genparamlib_yaml
from nodl_schema import parse_nodl


def test_generate_genparamlib_yaml_preserves_integer_validation_values():
    doc = parse_nodl(
        """
        nodl_version: 2
        parameters:
          count:
            type: int
            default_value: 3
            validation:
              bounds<>: [0, 10]
        """
    )
    assert doc.parameters is not None

    generated = generate_genparamlib_yaml('test_node', doc.parameters)
    data = yaml.safe_load(generated.content)
    parameter = data['test_node']['count']

    assert parameter['default_value'] == 3
    assert type(parameter['default_value']) is int
    assert parameter['validation']['bounds<>'] == [0, 10]
    assert [type(value) for value in parameter['validation']['bounds<>']] == [int, int]
