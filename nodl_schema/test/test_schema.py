# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NoDL schema loading and validation."""

import io
import json

import pytest
from jsonschema import ValidationError

from nodl_schema import dump_nodl, load_nodl, load_schema, validate
from nodl_schema.models import NodlDocument

_MIN_QOS = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}
_KEEP_LAST_QOS = {'history': 'KEEP_LAST', 'depth': 10, 'reliability': 'RELIABLE'}


# ---------------------------------------------------------------------------
# load_schema
# ---------------------------------------------------------------------------


def test_load_schema_returns_dict():
    schema = load_schema()
    assert isinstance(schema, dict)
    assert '$schema' in schema


def test_load_schema_cached():
    assert load_schema() is load_schema()


# ---------------------------------------------------------------------------
# Valid documents
# ---------------------------------------------------------------------------


def test_minimal_valid_document():
    validate({'nodl_version': 2})


def test_nodl_version_required():
    with pytest.raises(ValidationError):
        validate({})


def test_description_field():
    validate({'nodl_version': 2, 'description': 'A simple node'})


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
    validate({'nodl_version': 2, 'parameters': {'p': {'type': ptype, 'default_value': default}}})


def test_parameter_without_default():
    validate({'nodl_version': 2, 'parameters': {'p': {'type': 'string'}}})


def test_parameter_with_all_fields():
    validate({
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
    validate({
        'nodl_version': 2,
        'publishers': [{'name': '/chatter', 'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}],
    })


def test_publisher_with_keep_last_qos():
    validate({
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
    validate({
        'nodl_version': 2,
        'publishers': [{'name': '/t', 'type': 'std_msgs/String', 'qos': _MIN_QOS}],
    })


def test_qos_keep_all():
    validate({
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
    validate({
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
    validate({
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
    validate({
        'nodl_version': 2,
        'subscriptions': [{'name': '/input', 'type': 'sensor_msgs/msg/Image', 'qos': _MIN_QOS}],
    })


def test_service_servers_and_clients():
    validate({
        'nodl_version': 2,
        'service_servers': [{'name': '/set_bool', 'type': 'std_srvs/srv/SetBool'}],
        'service_clients': [{'name': '/remote', 'type': 'std_srvs/srv/Trigger'}],
    })


def test_service_with_qos():
    validate({
        'nodl_version': 2,
        'service_servers': [{'name': '/set_bool', 'type': 'std_srvs/srv/SetBool', 'qos': _MIN_QOS}],
    })


def test_action_servers_and_clients():
    validate({
        'nodl_version': 2,
        'action_servers': [{'name': '/navigate', 'type': 'nav2_msgs/action/NavigateToPose'}],
        'action_clients': [{'name': '/spin', 'type': 'nav2_msgs/action/Spin'}],
    })


def test_complete_document():
    validate({
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
        validate({'nodl_version': 2, 'unknown_key': 'value'})


def test_wrong_nodl_version_rejected():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 1})


def test_string_nodl_version_rejected():
    with pytest.raises(ValidationError):
        validate({'nodl_version': '2'})


def test_base_node_accepted():
    validate({'nodl_version': 2, 'base': 'node'})


def test_base_lifecycle_node_accepted():
    validate({'nodl_version': 2, 'base': 'lifecycle_node'})


def test_base_unknown_rejected():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'base': 'unknown_base'})


def test_fragments_accepted():
    validate({'nodl_version': 2, 'fragments': [{'ref': 'nodl://pkg/x'}]})


def test_fragment_missing_ref_rejected():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'fragments': [{'name': 'no_ref'}]})


def test_invalid_parameter_type():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'parameters': {'p': {'type': 'float'}}})


def test_parameter_missing_type():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'parameters': {'p': {'description': 'no type field'}}})


def test_invalid_type_format_double_slash():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'publishers': [{'name': '/t', 'type': 'std_msgs//String', 'qos': _MIN_QOS}]})


def test_qos_missing_reliability():
    with pytest.raises(ValidationError):
        validate({
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
        validate({
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
        validate({
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
        validate({
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
        validate({'nodl_version': 2, 'publishers': [{'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}]})


def test_publisher_missing_qos():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'publishers': [{'name': '/t', 'type': 'std_msgs/msg/String'}]})


def test_service_missing_type():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'service_servers': [{'name': '/s'}]})


def test_action_missing_name():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'action_servers': [{'type': 'nav2_msgs/action/NavigateToPose'}]})


# ---------------------------------------------------------------------------
# load_nodl
# ---------------------------------------------------------------------------


def test_load_nodl_from_yaml_string():
    yaml_text = (
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: /t\n'
        '    type: std_msgs/msg/String\n'
        '    qos:\n'
        '      history: SYSTEM_DEFAULT\n'
        '      reliability: SYSTEM_DEFAULT\n'
    )
    doc = load_nodl(yaml_text)
    assert isinstance(doc, NodlDocument)
    assert doc.publishers[0].name == '/t'


def test_load_nodl_from_json_string():
    data = {
        'nodl_version': 2,
        'publishers': [{'name': '/t', 'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}],
    }
    doc = load_nodl(json.dumps(data))
    assert doc.publishers[0].name == '/t'


def test_load_nodl_from_file_like():
    f = io.StringIO('nodl_version: 2\nparameters:\n  p:\n    type: string\n')
    doc = load_nodl(f)
    assert 'p' in doc.parameters


def test_load_nodl_invalid_raises():
    with pytest.raises(ValidationError):
        load_nodl('nodl_version: 2\nparameters:\n  p:\n    type: bad_type\n')


# ---------------------------------------------------------------------------
# dump_nodl
# ---------------------------------------------------------------------------


def test_dump_nodl_yaml_from_dict():
    result = dump_nodl({'nodl_version': 2})
    assert 'nodl_version' in result and '2' in result


def test_dump_nodl_yaml_from_document():
    doc = NodlDocument(nodl_version=2)
    result = dump_nodl(doc)
    assert 'nodl_version' in result and '2' in result


def test_dump_nodl_json():
    parsed = json.loads(dump_nodl({'nodl_version': 2}, format='json'))
    assert parsed['nodl_version'] == 2


def test_dump_nodl_json_from_document():
    doc = NodlDocument(nodl_version=2)
    parsed = json.loads(dump_nodl(doc, format='json'))
    assert parsed['nodl_version'] == 2
