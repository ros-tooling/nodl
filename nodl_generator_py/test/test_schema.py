# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for ``codegen.python`` validation."""

import pytest
from jsonschema import ValidationError

from nodl_generator_py.models import CodegenPython, Role
from nodl_generator_py.schema import load, validate


def _base(**overrides):
    value = {'role': 'BASE_CLASS', 'module': 'rclpy.node', 'class': 'Node'}
    value.update(overrides)
    return {'python': value}


def test_load_base_class_defaults_publisher_method():
    config = load(_base())
    assert isinstance(config, CodegenPython)
    assert config.role is Role.BASE_CLASS
    assert config.module == 'rclpy.node'
    assert config.class_ == 'Node'
    assert config.publisher_method == 'create_publisher'


@pytest.mark.parametrize(
    'codegen',
    [
        _base(role='OTHER'),
        _base(module='bad-module'),
        _base(module='rclpy.class'),
        _base(**{'class': '123Node'}),
        _base(**{'class': 'class'}),
        _base(publisher_method='not-valid'),
        _base(publisher_method='for'),
        _base(extra=True),
        {'python': {'role': 'BASE_CLASS', 'module': 'rclpy.node'}},
    ],
)
def test_invalid_metadata_fails(codegen):
    with pytest.raises(ValidationError):
        validate(codegen)


def test_other_language_metadata_is_ignored():
    assert load({'cpp': {'role': 'BASE_CLASS'}}) is None
