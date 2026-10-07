# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for codegen.cpp schema validation and loading."""

import pytest
from jsonschema import ValidationError

from nodl_generator_cpp.generate import CODEGEN_CPP_SCHEMA
from nodl_generator_cpp.models import CodegenCpp, Role

CODEGEN_KEY = CODEGEN_CPP_SCHEMA.key
load = CODEGEN_CPP_SCHEMA.load

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestValidate:
    """Tests for schema validation through load()."""

    def test_valid_base_class(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'}}
        load(codegen)  # should not raise

    @pytest.mark.parametrize('namespace', [None, 'polymath_health', 'my_pkg::nodes', '_a::b1::c_2'])
    def test_valid_node(self, namespace):
        load({CODEGEN_KEY: {'role': 'NODE', **({'namespace': namespace} if namespace else {})}})

    @pytest.mark.parametrize('namespace', ['', '1bad', 'a::', '::a', 'a:b', 'a::1b', 'a b', 'a::::b'])
    def test_invalid_node_namespace(self, namespace):
        with pytest.raises(ValidationError):
            load({CODEGEN_KEY: {'role': 'NODE', 'namespace': namespace}})

    @pytest.mark.parametrize('field,value', [('class', 'rclcpp::Node'), ('header', 'rclcpp/rclcpp.hpp')])
    def test_node_rejects_base_class_fields(self, field, value):
        with pytest.raises(ValidationError):
            load({CODEGEN_KEY: {'role': 'NODE', field: value}})

    @pytest.mark.parametrize(
        'config',
        [
            {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'},
            {'role': 'NO_GENERATE'},
        ],
    )
    def test_namespace_only_valid_on_node(self, config):
        with pytest.raises(ValidationError, match='namespace'):
            load({CODEGEN_KEY: {**config, 'namespace': 'ns'}})

    def test_valid_no_generate(self):
        load({CODEGEN_KEY: {'role': 'NO_GENERATE'}})

    def test_no_cpp_key_is_ok(self):
        load({})  # no cpp key — nothing to validate
        load({'python': {'something': 'else'}})  # other languages are fine

    def test_unknown_role(self):
        codegen = {CODEGEN_KEY: {'role': 'unknown_thing', 'class': 'Foo', 'header': 'foo.hpp'}}
        with pytest.raises(ValidationError, match='unknown_thing'):
            load(codegen)

    def test_missing_role(self):
        codegen = {CODEGEN_KEY: {'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'}}
        with pytest.raises(ValidationError, match="'role' is a required property"):
            load(codegen)

    def test_base_class_missing_class(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'header': 'rclcpp/rclcpp.hpp'}}
        with pytest.raises(ValidationError, match="'class' is a required property"):
            load(codegen)

    def test_base_class_missing_header(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node'}}
        with pytest.raises(ValidationError, match="'header' is a required property"):
            load(codegen)

    @pytest.mark.parametrize('field,value', [('class', 'Ignored'), ('header', 'ignored.hpp')])
    def test_no_generate_rejects_base_class_fields(self, field, value):
        codegen = {CODEGEN_KEY: {'role': 'NO_GENERATE', field: value}}
        with pytest.raises(ValidationError):
            load(codegen)

    def test_extra_key_rejected(self):
        codegen = {
            CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp', 'extra': True}
        }
        with pytest.raises(ValidationError, match='extra'):
            load(codegen)

    def test_invalid_class_pattern(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': '123bad', 'header': 'foo.hpp'}}
        with pytest.raises(ValidationError, match='123bad'):
            load(codegen)


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


class TestLoad:
    """Tests for the load() function."""

    def test_returns_model(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'}}
        result = load(codegen)
        assert isinstance(result, CodegenCpp)
        assert result.role == Role.BASE_CLASS
        assert result.class_ == 'rclcpp::Node'
        assert result.header == 'rclcpp/rclcpp.hpp'

    def test_returns_no_generate_model(self):
        result = load({CODEGEN_KEY: {'role': 'NO_GENERATE'}})
        assert isinstance(result, CodegenCpp)
        assert result.role is Role.NO_GENERATE
        assert result.class_ is None
        assert result.header is None

    def test_returns_node_model(self):
        result = load({CODEGEN_KEY: {'role': 'NODE', 'namespace': 'my_pkg::nodes'}})
        assert isinstance(result, CodegenCpp)
        assert result.role is Role.NODE
        assert result.namespace == 'my_pkg::nodes'

    def test_returns_none_when_no_cpp(self):
        assert load({}) is None
        assert load({'python': {'role': 'something'}}) is None

    def test_raises_on_invalid(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS'}}  # missing class and header
        with pytest.raises(ValidationError):
            load(codegen)
