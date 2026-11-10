# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import copy

from nodl_runtime_py.parameters import copy_parameters, parameter_values, values_equal


class _Params:
    """Mimics the parameter object of generate_parameter_library_py, which shares a nested struct between copies."""

    class _Colour:
        r = 0.8
        g = 0.4

    stamp_ = 0
    speed = 1.5
    name = 'bot'
    weights = [1.0, 2.0]
    colour = _Colour()

    def reset(self):
        pass


def _params():
    _Params.weights = [1.0, 2.0]
    _Params.colour = _Params._Colour()
    params = _Params()
    params.stamp_ = 7
    return params


def test_values_are_nested_and_leave_out_stamp_and_methods():
    assert parameter_values(_params()) == {
        'speed': 1.5,
        'name': 'bot',
        'weights': [1.0, 2.0],
        'colour': {'r': 0.8, 'g': 0.4},
    }


def test_values_share_nothing_with_the_parameters():
    params = _params()
    values = parameter_values(params)

    params.weights.append(3.0)

    assert values['weights'] == [1.0, 2.0]


def test_copy_keeps_values_and_stamp():
    params = _params()

    result = copy_parameters(params)

    assert result.stamp_ == 7
    assert parameter_values(result) == parameter_values(params)


def test_copy_owns_nested_structs_and_lists():
    params = _params()
    shared = copy.copy(params)
    assert shared.colour is params.colour

    result = copy_parameters(params)
    params.colour.r = 0.1
    params.weights.append(3.0)

    assert result.colour is not params.colour
    assert result.colour.r == 0.8
    assert result.weights == [1.0, 2.0]


def test_equal_values_ignore_nested_identity():
    assert values_equal(parameter_values(_params()), parameter_values(_params()))


def test_nested_and_list_differences_are_detected():
    first = parameter_values(_params())
    nested = parameter_values(_params())
    nested['colour']['r'] = 0.5
    listed = parameter_values(_params())
    listed['weights'] = [1.0, 2.5]
    longer = parameter_values(_params())
    longer['weights'] = [1.0, 2.0, 3.0]

    assert not values_equal(first, nested)
    assert not values_equal(first, listed)
    assert not values_equal(first, longer)


def test_nan_equals_nan_at_every_depth():
    nan = float('nan')

    assert values_equal(
        {'x': nan, 'a': {'y': nan}, 'l': [nan]}, {'x': float('nan'), 'a': {'y': float('nan')}, 'l': [float('nan')]}
    )
    assert not values_equal({'x': nan}, {'x': 1.0})
