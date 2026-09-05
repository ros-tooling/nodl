# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import pytest

from nodl_generator_common.naming import camel_to_snake, to_member_name


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('NavigateToPose', 'navigate_to_pose'),
        ('SetBool', 'set_bool'),
        ('String', 'string'),
        ('GetParameters', 'get_parameters'),
        ('HTTPServer', 'http_server'),
        ('already_snake', 'already_snake'),
    ],
)
def test_camel_to_snake(name, expected):
    assert camel_to_snake(name) == expected


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('/rosout', 'rosout'),
        ('~/describe_parameters', 'describe_parameters'),
        ('cmd_vel', 'cmd_vel'),
        ('/a/b/c', 'a_b_c'),
        ('~/a/b', 'a_b'),
    ],
)
def test_to_member_name(name, expected):
    assert to_member_name(name) == expected
