# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for codegen.cpp schema validation and loading."""

import pytest
from jsonschema import ValidationError

from nodl_generator_cpp.models import CodegenCpp, Role
from nodl_generator_cpp.schema import CODEGEN_KEY, load, validate

# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


class TestValidate:
    """Tests for the validate() function."""

    def test_valid_base_class(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'}}
        validate(codegen)  # should not raise

    def test_no_cpp_key_is_ok(self):
        validate({})  # no cpp key — nothing to validate
        validate({'python': {'something': 'else'}})  # other languages are fine

    def test_unknown_role(self):
        codegen = {CODEGEN_KEY: {'role': 'unknown_thing', 'class': 'Foo', 'header': 'foo.hpp'}}
        with pytest.raises(ValidationError, match='unknown_thing'):
            validate(codegen)

    def test_missing_role(self):
        codegen = {CODEGEN_KEY: {'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'}}
        with pytest.raises(ValidationError, match="'role' is a required property"):
            validate(codegen)

    def test_base_class_missing_class(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'header': 'rclcpp/rclcpp.hpp'}}
        with pytest.raises(ValidationError, match="'class' is a required property"):
            validate(codegen)

    def test_base_class_missing_header(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node'}}
        with pytest.raises(ValidationError, match="'header' is a required property"):
            validate(codegen)

    def test_extra_key_rejected(self):
        codegen = {
            CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp', 'extra': True}
        }
        with pytest.raises(ValidationError, match='extra'):
            validate(codegen)

    def test_invalid_class_pattern(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS', 'class': '123bad', 'header': 'foo.hpp'}}
        with pytest.raises(ValidationError, match='123bad'):
            validate(codegen)


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

    def test_returns_none_when_no_cpp(self):
        assert load({}) is None
        assert load({'python': {'role': 'something'}}) is None

    def test_raises_on_invalid(self):
        codegen = {CODEGEN_KEY: {'role': 'BASE_CLASS'}}  # missing class and header
        with pytest.raises(ValidationError):
            load(codegen)
