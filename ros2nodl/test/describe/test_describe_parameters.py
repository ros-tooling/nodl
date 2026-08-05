# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest
import stub_msgs

from nodl_schema.models import ArrayType, ScalarType
from ros2nodl.describe._transform import parameter_definition


@pytest.mark.parametrize(
    'source,expected',
    [
        (stub_msgs.PARAMETER_NOT_SET, ScalarType.none),
        (stub_msgs.PARAMETER_BOOL, ScalarType.bool),
        (stub_msgs.PARAMETER_INTEGER, ScalarType.int),
        (stub_msgs.PARAMETER_DOUBLE, ScalarType.double),
        (stub_msgs.PARAMETER_STRING, ScalarType.string),
        (stub_msgs.PARAMETER_BYTE_ARRAY, ArrayType.byte_array),
        (stub_msgs.PARAMETER_BOOL_ARRAY, ArrayType.bool_array),
        (stub_msgs.PARAMETER_INTEGER_ARRAY, ArrayType.int_array),
        (stub_msgs.PARAMETER_DOUBLE_ARRAY, ArrayType.double_array),
        (stub_msgs.PARAMETER_STRING_ARRAY, ArrayType.string_array),
    ],
)
def test_parameter_type_mapping(source, expected):
    assert parameter_definition(stub_msgs.descriptor('p', source)).type is expected


@pytest.mark.parametrize(
    'type,field,value',
    [
        (stub_msgs.PARAMETER_BOOL, 'bool_value', True),
        (stub_msgs.PARAMETER_INTEGER, 'integer_value', 42),
        (stub_msgs.PARAMETER_DOUBLE, 'double_value', 1.5),
        (stub_msgs.PARAMETER_STRING, 'string_value', 'hello'),
        (stub_msgs.PARAMETER_BYTE_ARRAY, 'byte_array_value', [0, 1, 127, 255]),
        (stub_msgs.PARAMETER_INTEGER_ARRAY, 'integer_array_value', [1, 2]),
        (stub_msgs.PARAMETER_STRING_ARRAY, 'string_array_value', ['a', 'b']),
    ],
)
def test_default_value_mapping(type, field, value):
    definition = parameter_definition(
        stub_msgs.descriptor('p', type),
        stub_msgs.value(type, **{field: value}),
    )
    assert definition.default_value == value


def test_not_set_descriptor_uses_value_type():
    definition = parameter_definition(
        stub_msgs.descriptor('p', stub_msgs.PARAMETER_NOT_SET),
        stub_msgs.value(stub_msgs.PARAMETER_INTEGER, integer_value=7),
    )
    assert definition.type is ScalarType.int
    assert definition.default_value == 7


def test_mismatched_value_is_omitted():
    definition = parameter_definition(
        stub_msgs.descriptor('p', stub_msgs.PARAMETER_STRING),
        stub_msgs.value(stub_msgs.PARAMETER_INTEGER, integer_value=7),
    )
    assert definition.default_value is None


@pytest.mark.parametrize(
    'range_field,range_value',
    [
        ('floating_point_range', stub_msgs.fp_range(0.5, 2.5)),
        ('integer_range', stub_msgs.int_range(1, 5)),
    ],
)
def test_range_and_metadata(range_field, range_value):
    definition = parameter_definition(
        stub_msgs.descriptor(
            'p',
            stub_msgs.PARAMETER_DOUBLE,
            description='speed',
            additional_constraints='positive',
            read_only=True,
            **{range_field: range_value},
        )
    )
    assert definition.validation.bounds == [range_value.from_value, range_value.to_value]
    assert definition.description == 'speed'
    assert definition.additional_constraints == 'positive'
    assert definition.read_only is True
