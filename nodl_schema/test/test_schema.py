# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NoDL schema loading and validation."""

import io
import json

import pytest
from jsonschema import ValidationError

from nodl_schema import dump_nodl, load_interface, load_interface_schema, validate_interface, validate_node
from nodl_schema.models import Interface

_MIN_QOS = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}
_KEEP_LAST_QOS = {'history': 'KEEP_LAST', 'depth': 10, 'reliability': 'RELIABLE'}


# ---------------------------------------------------------------------------
# load_interface_schema
# ---------------------------------------------------------------------------


def test_load_interface_schema_returns_dict():
    schema = load_interface_schema()
    assert isinstance(schema, dict)
    assert '$schema' in schema


def test_load_interface_schema_cached():
    assert load_interface_schema() is load_interface_schema()


# ---------------------------------------------------------------------------
# Valid documents
# ---------------------------------------------------------------------------


def test_minimal_valid_document():
    validate_interface({'nodl_version': 2})


def test_nodl_version_required():
    with pytest.raises(ValidationError):
        validate_interface({})


def test_description_field():
    validate_interface({'nodl_version': 2, 'description': 'A simple node'})


@pytest.mark.parametrize(
    'ptype,default',
    [
        ('bool', True),
        ('int', 42),
        ('double', 3.14),
        ('string', 'hello'),
        ('bool_array', [True, False]),
        ('int_array', [1, 2, 3]),
        ('double_array', [1.0, 2.0]),
        ('string_array', ['a', 'b']),
    ],
)
def test_parameter_types(ptype, default):
    validate_interface({'nodl_version': 2, 'parameters': {'p': {'type': ptype, 'default_value': default}}})


def test_parameter_without_default():
    validate_interface({'nodl_version': 2, 'parameters': {'p': {'type': 'string'}}})


def test_parameter_with_all_fields():
    validate_interface({
        'nodl_version': 2,
        'parameters': {
            'speed': {
                'type': 'double',
                'default_value': 1.0,
                'description': 'Max speed in m/s',
                'read_only': True,
                'additional_constraints': 'Must be positive',
            }
        },
    })


def test_publisher_minimal():
    validate_interface({
        'nodl_version': 2,
        'publishers': [{'name': '/chatter', 'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}],
    })


def test_publisher_with_keep_last_qos():
    validate_interface({
        'nodl_version': 2,
        'publishers': [
            {
                'name': '/chatter',
                'type': 'std_msgs/msg/String',
                'description': 'Chat messages',
                'qos': _KEEP_LAST_QOS,
            }
        ],
    })


def test_publisher_type_without_middle_namespace():
    validate_interface({
        'nodl_version': 2,
        'publishers': [{'name': '/t', 'type': 'std_msgs/String', 'qos': _MIN_QOS}],
    })


def test_qos_keep_all():
    validate_interface({
        'nodl_version': 2,
        'publishers': [
            {
                'name': '/t',
                'type': 'std_msgs/msg/String',
                'qos': {'history': 'KEEP_ALL', 'reliability': 'BEST_EFFORT'},
            }
        ],
    })


def test_qos_full():
    validate_interface({
        'nodl_version': 2,
        'publishers': [
            {
                'name': '/t',
                'type': 'std_msgs/msg/String',
                'qos': {
                    'history': 'KEEP_LAST',
                    'depth': 10,
                    'reliability': 'RELIABLE',
                    'durability': 'TRANSIENT_LOCAL',
                    'deadline_ns': 100_000_000,
                    'lifespan_ns': 200_000_000,
                    'liveliness': 'AUTOMATIC',
                    'liveliness_lease_duration_ns': 1_000_000_000,
                },
            }
        ],
    })


def test_qos_best_available():
    validate_interface({
        'nodl_version': 2,
        'publishers': [
            {
                'name': '/t',
                'type': 'std_msgs/msg/String',
                'qos': {'history': 'KEEP_LAST', 'depth': 5, 'reliability': 'BEST_AVAILABLE'},
            }
        ],
    })


def test_subscriptions():
    validate_interface({
        'nodl_version': 2,
        'subscriptions': [{'name': '/input', 'type': 'sensor_msgs/msg/Image', 'qos': _MIN_QOS}],
    })


def test_service_servers_and_clients():
    validate_interface({
        'nodl_version': 2,
        'service_servers': [{'name': '/set_bool', 'type': 'std_srvs/srv/SetBool'}],
        'service_clients': [{'name': '/remote', 'type': 'std_srvs/srv/Trigger'}],
    })


def test_service_with_qos():
    validate_interface({
        'nodl_version': 2,
        'service_servers': [{'name': '/set_bool', 'type': 'std_srvs/srv/SetBool', 'qos': _MIN_QOS}],
    })


def test_action_servers_and_clients():
    validate_interface({
        'nodl_version': 2,
        'action_servers': [{'name': '/navigate', 'type': 'nav2_msgs/action/NavigateToPose'}],
        'action_clients': [{'name': '/spin', 'type': 'nav2_msgs/action/Spin'}],
    })


def test_complete_document():
    validate_interface({
        'nodl_version': 2,
        'description': 'A mobile base controller node',
        'parameters': {
            'max_vel': {'type': 'double', 'default_value': 1.0, 'description': 'Max velocity'},
            'name': {'type': 'string', 'read_only': True},
        },
        'publishers': [
            {'name': '/cmd_vel', 'type': 'geometry_msgs/msg/Twist', 'qos': _KEEP_LAST_QOS},
        ],
        'subscriptions': [
            {
                'name': '/odom',
                'type': 'nav_msgs/msg/Odometry',
                'qos': {'history': 'KEEP_LAST', 'depth': 1, 'reliability': 'BEST_EFFORT', 'durability': 'VOLATILE'},
            },
        ],
        'service_servers': [{'name': '/reset', 'type': 'std_srvs/srv/Trigger'}],
        'service_clients': [{'name': '/set_mode', 'type': 'std_srvs/srv/SetBool'}],
        'action_servers': [{'name': '/navigate', 'type': 'nav2_msgs/action/NavigateToPose'}],
        'action_clients': [{'name': '/spin', 'type': 'nav2_msgs/action/Spin'}],
    })


# ---------------------------------------------------------------------------
# Invalid documents
# ---------------------------------------------------------------------------


def test_unknown_top_level_key_rejected():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 2, 'unknown_key': 'value'})


def test_wrong_nodl_version_rejected():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 1})


def test_string_nodl_version_rejected():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': '2'})


def test_interface_rejects_composition_keys():
    # Composition lives on the node schema; interface definitions must not carry base/main/mixins.
    for key, value in (('base', 'node'), ('main', {'nodl_version': 2}), ('mixins', ['nodl://pkg/x'])):
        with pytest.raises(ValidationError):
            validate_interface({'nodl_version': 2, key: value})


# ---------------------------------------------------------------------------
# validate_node -- the Node composition schema
# ---------------------------------------------------------------------------


def test_node_minimal_accepted():
    validate_node({'nodl_version': 2, 'main': {'nodl_version': 2}})


def test_node_with_base_and_mixins_accepted():
    validate_node({
        'nodl_version': 2,
        'base': 'lifecycle_node',
        'main': {
            'nodl_version': 2,
            'publishers': [{'name': '~/s', 'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}],
        },
        'mixins': ['nodl://pkg/telemetry', {'nodl_version': 2}],
    })


def test_node_missing_main_rejected():
    with pytest.raises(ValidationError):
        validate_node({'nodl_version': 2, 'base': 'node'})


def test_node_unknown_base_rejected():
    with pytest.raises(ValidationError):
        validate_node({'nodl_version': 2, 'main': {'nodl_version': 2}, 'base': 'nope'})


def test_node_main_must_be_valid_document():
    # main is validated against the document schema; an unknown key fails.
    with pytest.raises(ValidationError):
        validate_node({'nodl_version': 2, 'main': {'nodl_version': 2, 'bogus': 1}})


def test_node_mixin_scalar_rejected():
    # A mixin entry must be a ref string or an in-place document, not a bare scalar.
    with pytest.raises(ValidationError):
        validate_node({'nodl_version': 2, 'main': {'nodl_version': 2}, 'mixins': [5]})


def test_invalid_parameter_type():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 2, 'parameters': {'p': {'type': 'float'}}})


def test_parameter_missing_type():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 2, 'parameters': {'p': {'description': 'no type field'}}})


def test_invalid_type_format_double_slash():
    with pytest.raises(ValidationError):
        validate_interface({
            'nodl_version': 2,
            'publishers': [{'name': '/t', 'type': 'std_msgs//String', 'qos': _MIN_QOS}],
        })


def test_qos_missing_reliability():
    with pytest.raises(ValidationError):
        validate_interface({
            'nodl_version': 2,
            'publishers': [
                {
                    'name': '/t',
                    'type': 'std_msgs/msg/String',
                    'qos': {'history': 'KEEP_LAST', 'depth': 10},
                }
            ],
        })


def test_qos_missing_history():
    with pytest.raises(ValidationError):
        validate_interface({
            'nodl_version': 2,
            'publishers': [
                {
                    'name': '/t',
                    'type': 'std_msgs/msg/String',
                    'qos': {'reliability': 'RELIABLE'},
                }
            ],
        })


def test_qos_invalid_reliability_value():
    with pytest.raises(ValidationError):
        validate_interface({
            'nodl_version': 2,
            'publishers': [
                {
                    'name': '/t',
                    'type': 'std_msgs/msg/String',
                    'qos': {'history': 'KEEP_LAST', 'depth': 10, 'reliability': 'MEDIUM_EFFORT'},
                }
            ],
        })


def test_keep_last_without_depth_rejected():
    with pytest.raises(ValidationError):
        validate_interface({
            'nodl_version': 2,
            'publishers': [
                {
                    'name': '/t',
                    'type': 'std_msgs/msg/String',
                    'qos': {'history': 'KEEP_LAST', 'reliability': 'RELIABLE'},
                }
            ],
        })


def test_publisher_missing_name():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 2, 'publishers': [{'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}]})


def test_publisher_missing_qos():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 2, 'publishers': [{'name': '/t', 'type': 'std_msgs/msg/String'}]})


def test_service_missing_type():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 2, 'service_servers': [{'name': '/s'}]})


def test_action_missing_name():
    with pytest.raises(ValidationError):
        validate_interface({'nodl_version': 2, 'action_servers': [{'type': 'nav2_msgs/action/NavigateToPose'}]})


# ---------------------------------------------------------------------------
# load_interface
# ---------------------------------------------------------------------------


def test_load_interface_from_yaml_string():
    yaml_text = (
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: /t\n'
        '    type: std_msgs/msg/String\n'
        '    qos:\n'
        '      history: SYSTEM_DEFAULT\n'
        '      reliability: SYSTEM_DEFAULT\n'
    )
    doc = load_interface(yaml_text)
    assert isinstance(doc, Interface)
    assert doc.publishers[0].name == '/t'


def test_load_interface_from_json_string():
    data = {
        'nodl_version': 2,
        'publishers': [{'name': '/t', 'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}],
    }
    doc = load_interface(json.dumps(data))
    assert doc.publishers[0].name == '/t'


def test_load_interface_from_file_like():
    f = io.StringIO('nodl_version: 2\nparameters:\n  p:\n    type: string\n')
    doc = load_interface(f)
    assert 'p' in doc.parameters


def test_load_interface_invalid_raises():
    with pytest.raises(ValidationError):
        load_interface('nodl_version: 2\nparameters:\n  p:\n    type: bad_type\n')


# ---------------------------------------------------------------------------
# dump_nodl
# ---------------------------------------------------------------------------


def test_dump_nodl_yaml_from_dict():
    result = dump_nodl({'nodl_version': 2})
    assert 'nodl_version' in result and '2' in result


def test_dump_nodl_yaml_from_document():
    doc = Interface(nodl_version=2)
    result = dump_nodl(doc)
    assert 'nodl_version' in result and '2' in result


def test_dump_nodl_json():
    parsed = json.loads(dump_nodl({'nodl_version': 2}, format='json'))
    assert parsed['nodl_version'] == 2


def test_dump_nodl_json_from_document():
    doc = Interface(nodl_version=2)
    parsed = json.loads(dump_nodl(doc, format='json'))
    assert parsed['nodl_version'] == 2
