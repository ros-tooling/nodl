# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest

from nodl_generator_common.parameters import nest_dotted_parameters


def test_nest_dotted_parameters_groups_namespaces_and_preserves_order():
    definitions = {
        'enabled': 'enabled definition',
        'colour.r': 'red definition',
        'colour.g': 'green definition',
        'camera.exposure.auto': 'auto exposure definition',
    }

    assert nest_dotted_parameters(definitions) == {
        'enabled': 'enabled definition',
        'colour': {
            'r': 'red definition',
            'g': 'green definition',
        },
        'camera': {
            'exposure': {
                'auto': 'auto exposure definition',
            },
        },
    }


@pytest.mark.parametrize('name', ['', '.colour', 'colour.', 'colour..r'])
def test_nest_dotted_parameters_rejects_empty_name_components(name):
    with pytest.raises(ValueError, match='components cannot be empty'):
        nest_dotted_parameters({name: object()})


@pytest.mark.parametrize(
    'parameters',
    [
        {'colour': object(), 'colour.r': object()},
        {'colour.r': object(), 'colour': object()},
        {'camera.exposure.auto': object(), 'camera.exposure': object()},
    ],
)
def test_nest_dotted_parameters_rejects_namespace_conflicts(parameters):
    with pytest.raises(ValueError, match='cannot also be a parameter namespace'):
        nest_dotted_parameters(parameters)
