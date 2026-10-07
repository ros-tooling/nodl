# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for codegen.cpp schema validation and loading."""

import pytest
from jsonschema import ValidationError
from jsonschema.validators import Draft7Validator

from nodl_generator_cpp.generate import CODEGEN_CPP_SCHEMA
from nodl_generator_cpp.models import CodegenBaseClass, CodegenNode, CodegenNoGenerate
from nodl_schema.schema import load_schema_file

CODEGEN_KEY = CODEGEN_CPP_SCHEMA.key
load = CODEGEN_CPP_SCHEMA.load

_BASE_CLASS = {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'}

_VALID = [
    _BASE_CLASS,
    {'role': 'NO_GENERATE'},
    {'role': 'NODE'},
    {'role': 'NODE', 'namespace': 'my_pkg::nodes'},
]

_INVALID = [
    {},
    {'role': 'unknown'},
    {'role': 5},
    {'role': 'BASE_CLASS', 'class': 'rclcpp::Node'},
    {'role': 'BASE_CLASS', 'header': 'rclcpp/rclcpp.hpp'},
    {**_BASE_CLASS, 'namespace': 'ns'},
    {**_BASE_CLASS, 'extra': True},
    {'role': 'NO_GENERATE', 'class': 'Ignored'},
    {'role': 'NO_GENERATE', 'header': 'ignored.hpp'},
    {'role': 'NODE', 'class': 'rclcpp::Node'},
    {'role': 'NODE', 'header': 'rclcpp/rclcpp.hpp'},
    {'role': 'NODE', 'namespace': '1bad'},
]

# ---------------------------------------------------------------------------
# The full oneOf schema
# ---------------------------------------------------------------------------


class TestFullSchema:
    """The schema as a whole agrees with load(), which only checks the variant selected by ``role``."""

    def test_schema_is_valid_draft7(self):
        Draft7Validator.check_schema(load_schema_file(CODEGEN_CPP_SCHEMA.schema))

    @pytest.mark.parametrize('cpp', _VALID)
    def test_valid_cases_match_exactly_one_variant(self, cpp):
        Draft7Validator(load_schema_file(CODEGEN_CPP_SCHEMA.schema)).validate(cpp)
        load({CODEGEN_KEY: cpp})

    @pytest.mark.parametrize('cpp', _INVALID)
    def test_invalid_cases_rejected(self, cpp):
        with pytest.raises(ValidationError):
            Draft7Validator(load_schema_file(CODEGEN_CPP_SCHEMA.schema)).validate(cpp)
        with pytest.raises(ValidationError):
            load({CODEGEN_KEY: cpp})


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestValidate:
    """Tests for schema validation through load()."""

    def test_valid_base_class(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'}}
        load(codegen)  # should not raise

    def test_valid_no_generate(self):
        load({CODEGEN_KEY: {'role': 'NO_GENERATE'}})

    def test_valid_node_without_namespace(self):
        load({CODEGEN_KEY: {'role': 'NODE'}})

    @pytest.mark.parametrize('namespace', ['polymath_health', 'my_pkg::nodes', '_a::b1::c_2'])
    def test_valid_node_namespace(self, namespace):
        load({CODEGEN_KEY: {'role': 'NODE', 'namespace': namespace}})

    @pytest.mark.parametrize('namespace', ['', '1bad', 'a::', '::a', 'a:b', 'a::1b', 'a b', 'a::::b'])
    def test_invalid_node_namespace(self, namespace):
        with pytest.raises(ValidationError):
            load({CODEGEN_KEY: {'role': 'NODE', 'namespace': namespace}})

    @pytest.mark.parametrize('field,value', [('class', 'rclcpp::Node'), ('header', 'rclcpp/rclcpp.hpp')])
    def test_node_rejects_base_class_fields(self, field, value):
        with pytest.raises(ValidationError):
            load({CODEGEN_KEY: {'role': 'NODE', field: value}})

    @pytest.mark.parametrize('role', ['BASE_CLASS', 'NO_GENERATE'])
    def test_namespace_only_valid_on_node(self, role):
        codegen = {CODEGEN_KEY: {'role': role, 'namespace': 'ns'}}
        if role == 'BASE_CLASS':
            codegen[CODEGEN_KEY].update({'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'})
        with pytest.raises(ValidationError, match='namespace'):
            load(codegen)

    def test_non_object_rejected(self):
        with pytest.raises(ValidationError, match='object'):
            load({CODEGEN_KEY: 'NODE'})

    def test_no_cpp_key_is_ok(self):
        load({})  # no cpp key — nothing to validate
        load({'python': {'something': 'else'}})  # other languages are fine

    def test_unknown_role(self):
        codegen = {CODEGEN_KEY: {'role': 'unknown_thing', 'class': 'Foo', 'header': 'foo.hpp'}}
        with pytest.raises(ValidationError, match='unknown_thing'):
            load(codegen)

    def test_unknown_role_lists_valid_roles(self):
        with pytest.raises(ValidationError, match='BASE_CLASS.*NO_GENERATE.*NODE'):
            load({CODEGEN_KEY: {'role': 'nope'}})

    def test_non_string_role(self):
        with pytest.raises(ValidationError, match='5 is not one of'):
            load({CODEGEN_KEY: {'role': 5}})

    @pytest.mark.parametrize('role', [['NODE'], {'NODE': 1}])
    def test_unhashable_role(self, role):
        with pytest.raises(ValidationError, match='is not one of'):
            load({CODEGEN_KEY: {'role': role}})

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
        with pytest.raises(ValidationError, match=field):
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
        assert isinstance(result, CodegenBaseClass)
        assert result.class_ == 'rclcpp::Node'
        assert result.header == 'rclcpp/rclcpp.hpp'

    def test_returns_no_generate_model(self):
        result = load({CODEGEN_KEY: {'role': 'NO_GENERATE'}})
        assert isinstance(result, CodegenNoGenerate)

    def test_returns_node_model(self):
        result = load({CODEGEN_KEY: {'role': 'NODE', 'namespace': 'my_pkg::nodes'}})
        assert isinstance(result, CodegenNode)
        assert result.namespace == 'my_pkg::nodes'

    def test_node_namespace_optional(self):
        result = load({CODEGEN_KEY: {'role': 'NODE'}})
        assert isinstance(result, CodegenNode)
        assert result.namespace is None

    def test_returns_none_when_no_cpp(self):
        assert load({}) is None
        assert load({'python': {'role': 'something'}}) is None

    def test_raises_on_invalid(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS'}}  # missing class and header
        with pytest.raises(ValidationError):
            load(codegen)
