# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for generate_parameter_library input generation."""

import yaml

from nodl_generator_cpp.params import generate_genparamlib_yaml, generate_parameter_header
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


_NAMESPACED_PARAMETERS = """
    nodl_version: 2
    parameters:
      max_speed:
        type: double
        default_value: 1.5
      colour.r:
        type: double
        default_value: 0.8
    """


def test_generate_genparamlib_yaml_without_namespace_keys_on_target():
    doc = parse_nodl(_NAMESPACED_PARAMETERS)
    assert doc.parameters is not None

    data = yaml.safe_load(generate_genparamlib_yaml('my_node', doc.parameters).content)

    assert list(data) == ['my_node']


def test_generate_genparamlib_yaml_namespace_qualifies_top_key():
    doc = parse_nodl(_NAMESPACED_PARAMETERS)
    assert doc.parameters is not None

    data = yaml.safe_load(generate_genparamlib_yaml('my_node', doc.parameters, namespace='my_pkg::nodes').content)

    assert list(data) == ['my_pkg::nodes::my_node']
    assert set(data['my_pkg::nodes::my_node']) == {'max_speed', 'colour'}


def test_namespaced_parameter_header_declares_structs_in_namespace(tmp_path):
    doc = parse_nodl(_NAMESPACED_PARAMETERS)
    assert doc.parameters is not None
    yaml_file = tmp_path / 'my_node_parameters.yaml'
    yaml_file.write_text(generate_genparamlib_yaml('my_node', doc.parameters, namespace='my_pkg::nodes').content)

    header = generate_parameter_header(yaml_file).content

    assert 'namespace my_pkg::nodes::my_node {' in header
    assert '} // namespace my_pkg::nodes::my_node' in header
    # ROS parameter names do not include the namespace.
    assert 'prefix_ + "max_speed"' in header
    assert 'prefix_ + "colour.r"' in header
    assert 'prefix_ + "my_pkg' not in header
