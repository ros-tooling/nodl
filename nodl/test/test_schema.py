"""Unit tests for NoDL schema loading and validation."""

import pytest
from jsonschema import ValidationError

from nodl.schema import dump_nodl, load_nodl, load_schema, validate


def test_load_schema_returns_dict():
    schema = load_schema()
    assert isinstance(schema, dict)
    assert '$schema' in schema


def test_load_schema_cached():
    assert load_schema() is load_schema()


# ---------------------------------------------------------------------------
# Valid documents
# ---------------------------------------------------------------------------

def test_empty_document_is_valid():
    validate({})


def test_minimal_node():
    validate({'node': {'name': 'my_node'}})


def test_full_node_metadata():
    validate({'node': {'name': 'my_node', 'namespace': '/ns', 'package': 'my_pkg'}})


def test_parameter_types():
    for ptype, default in [
        ('bool', True),
        ('int', 42),
        ('double', 3.14),
        ('string', 'hello'),
        ('byte_array', [0, 128, 255]),
        ('bool_array', [True, False]),
        ('int_array', [1, 2, 3]),
        ('double_array', [1.0, 2.0]),
        ('string_array', ['a', 'b']),
    ]:
        validate({'parameters': {'p': {'type': ptype, 'default_value': default}}})


def test_parameter_without_default():
    validate({'parameters': {'p': {'type': 'string'}}})


def test_parameter_with_all_fields():
    validate({
        'parameters': {
            'speed': {
                'type': 'double',
                'default_value': 1.0,
                'description': 'Max speed in m/s',
                'read_only': True,
                'additional_constraints': 'Must be positive',
            }
        }
    })


def test_publisher_minimal():
    validate({
        'publishers': [{'topic': '/chatter', 'type': 'std_msgs/msg/String'}]
    })


def test_publisher_with_qos():
    validate({
        'publishers': [{
            'topic': '/chatter',
            'type': 'std_msgs/msg/String',
            'description': 'Chat messages',
            'qos': {'history': 10, 'reliability': 'RELIABLE'},
        }]
    })


def test_qos_keep_all():
    validate({
        'publishers': [{
            'topic': '/t',
            'type': 'std_msgs/msg/String',
            'qos': {'history': 'ALL', 'reliability': 'BEST_EFFORT'},
        }]
    })


def test_qos_full():
    validate({
        'publishers': [{
            'topic': '/t',
            'type': 'std_msgs/msg/String',
            'qos': {
                'history': 10,
                'reliability': 'RELIABLE',
                'durability': 'TRANSIENT_LOCAL',
                'deadline_ms': 100,
                'lifespan_ms': 200,
                'liveliness': 'AUTOMATIC',
                'lease_duration_ms': 1000,
            },
        }]
    })


def test_subscriptions():
    validate({
        'subscriptions': [{'topic': '/input', 'type': 'sensor_msgs/msg/Image'}]
    })


def test_service_servers_and_clients():
    validate({
        'service_servers': [{'name': '/set_bool', 'type': 'std_srvs/srv/SetBool'}],
        'service_clients': [{'name': '/remote', 'type': 'std_srvs/srv/Trigger'}],
    })


def test_action_servers_and_clients():
    validate({
        'action_servers': [{'name': '/navigate', 'type': 'nav2_msgs/action/NavigateToPose'}],
        'action_clients': [{'name': '/spin', 'type': 'nav2_msgs/action/Spin'}],
    })


def test_complete_document():
    validate({
        'nodl_version': '1',
        'node': {'name': 'my_node', 'namespace': '/ns', 'package': 'my_pkg'},
        'parameters': {
            'max_vel': {'type': 'double', 'default_value': 1.0, 'description': 'Max velocity'},
            'name': {'type': 'string', 'read_only': True},
        },
        'publishers': [
            {'topic': '/cmd_vel', 'type': 'geometry_msgs/msg/Twist',
             'qos': {'history': 10, 'reliability': 'RELIABLE'}},
        ],
        'subscriptions': [
            {'topic': '/odom', 'type': 'nav_msgs/msg/Odometry',
             'qos': {'history': 1, 'reliability': 'BEST_EFFORT', 'durability': 'VOLATILE'}},
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
        validate({'unknown_key': 'value'})


def test_invalid_parameter_type():
    with pytest.raises(ValidationError):
        validate({'parameters': {'p': {'type': 'float'}}})


def test_parameter_missing_type():
    with pytest.raises(ValidationError):
        validate({'parameters': {'p': {'description': 'no type field'}}})


def test_parameter_wrong_default_type_int_for_bool():
    with pytest.raises(ValidationError):
        validate({'parameters': {'p': {'type': 'bool', 'default_value': 42}}})


def test_parameter_wrong_default_type_string_for_int():
    with pytest.raises(ValidationError):
        validate({'parameters': {'p': {'type': 'int', 'default_value': 'not_an_int'}}})


def test_invalid_message_type_format():
    with pytest.raises(ValidationError):
        validate({'publishers': [{'topic': '/t', 'type': 'std_msgs/String'}]})


def test_invalid_service_type_format():
    with pytest.raises(ValidationError):
        validate({'service_servers': [{'name': '/s', 'type': 'std_srvs/Trigger'}]})


def test_invalid_action_type_format():
    with pytest.raises(ValidationError):
        validate({'action_servers': [{'name': '/a', 'type': 'nav2_msgs/NavigateToPose'}]})


def test_qos_missing_reliability():
    with pytest.raises(ValidationError):
        validate({
            'publishers': [{
                'topic': '/t',
                'type': 'std_msgs/msg/String',
                'qos': {'history': 10},
            }]
        })


def test_qos_missing_history():
    with pytest.raises(ValidationError):
        validate({
            'publishers': [{
                'topic': '/t',
                'type': 'std_msgs/msg/String',
                'qos': {'reliability': 'RELIABLE'},
            }]
        })


def test_qos_invalid_reliability_value():
    with pytest.raises(ValidationError):
        validate({
            'publishers': [{
                'topic': '/t',
                'type': 'std_msgs/msg/String',
                'qos': {'history': 10, 'reliability': 'MEDIUM_EFFORT'},
            }]
        })


def test_qos_zero_history_rejected():
    with pytest.raises(ValidationError):
        validate({
            'publishers': [{
                'topic': '/t',
                'type': 'std_msgs/msg/String',
                'qos': {'history': 0, 'reliability': 'RELIABLE'},
            }]
        })


def test_node_name_invalid_chars():
    with pytest.raises(ValidationError):
        validate({'node': {'name': '1bad-name'}})


def test_publisher_missing_topic():
    with pytest.raises(ValidationError):
        validate({'publishers': [{'type': 'std_msgs/msg/String'}]})


def test_publisher_missing_type():
    with pytest.raises(ValidationError):
        validate({'publishers': [{'topic': '/t'}]})


def test_service_missing_type():
    with pytest.raises(ValidationError):
        validate({'service_servers': [{'name': '/s'}]})


def test_action_missing_name():
    with pytest.raises(ValidationError):
        validate({'action_servers': [{'type': 'nav2_msgs/action/NavigateToPose'}]})


# ---------------------------------------------------------------------------
# load_nodl
# ---------------------------------------------------------------------------

def test_load_nodl_from_yaml_string():
    from nodl.models import NodlDocument
    yaml_text = "publishers:\n  - topic: /t\n    type: std_msgs/msg/String\n"
    doc = load_nodl(yaml_text)
    assert isinstance(doc, NodlDocument)
    assert doc.publishers[0].topic == '/t'


def test_load_nodl_from_json_string():
    json_text = '{"publishers": [{"topic": "/t", "type": "std_msgs/msg/String"}]}'
    doc = load_nodl(json_text, format='json')
    assert doc.publishers[0].topic == '/t'


def test_load_nodl_from_file_like():
    import io
    f = io.StringIO("parameters:\n  p:\n    type: string\n")
    doc = load_nodl(f)
    assert 'p' in doc.parameters


def test_load_nodl_invalid_raises():
    with pytest.raises(ValidationError):
        load_nodl("parameters:\n  p:\n    type: bad_type\n")


# ---------------------------------------------------------------------------
# dump_nodl
# ---------------------------------------------------------------------------

def test_dump_nodl_yaml_from_dict():
    data = {'node': {'name': 'n'}}
    result = dump_nodl(data)
    assert 'node' in result
    assert 'n' in result


def test_dump_nodl_yaml_from_document():
    from nodl.models import NodlDocument, NodeMetadata
    doc = NodlDocument(node=NodeMetadata(name='n'))
    result = dump_nodl(doc)
    assert 'node' in result
    assert 'n' in result


def test_dump_nodl_json():
    data = {'node': {'name': 'n'}}
    result = dump_nodl(data, format='json')
    import json
    parsed = json.loads(result)
    assert parsed['node']['name'] == 'n'


def test_dump_nodl_json_from_document():
    import json
    from nodl.models import NodlDocument, NodeMetadata
    doc = NodlDocument(node=NodeMetadata(name='n'))
    parsed = json.loads(dump_nodl(doc, format='json'))
    assert parsed['node']['name'] == 'n'
