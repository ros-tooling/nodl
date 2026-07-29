# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NoDL schema loading and validation."""

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


def test_fragments_no_longer_allowed():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'fragments': [{'ref': 'nodl://pkg/x'}]})


def test_base_no_longer_allowed():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'base': 'lifecycle_node'})


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
# includes — structural validation
# ---------------------------------------------------------------------------


def test_includes_valid_package_uri():
    validate({'nodl_version': 2, 'includes': [{'ref': 'nodl://pkg/name'}]})


def test_includes_valid_relative_path():
    validate({'nodl_version': 2, 'includes': [{'ref': './fragments/foo.nodl.yaml'}]})


def test_includes_with_other_fields():
    validate({
        'nodl_version': 2,
        'includes': [{'ref': 'nodl://pkg/name'}],
        'publishers': [{'name': '/t', 'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}],
        'parameters': {'p': {'type': 'string'}},
    })


def test_includes_empty_list():
    validate({'nodl_version': 2, 'includes': []})


def test_includes_bare_string_rejected():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'includes': ['nodl://pkg/x']})


def test_includes_missing_ref_rejected():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'includes': [{}]})


def test_includes_extra_key_rejected():
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'includes': [{'ref': 'nodl://pkg/x', 'bad': True}]})


@pytest.mark.parametrize(
    'ref',
    [
        'nodl://my_pkg/fragment_name',
        'nodl://my_pkg/some_long_name_123',
        './fragment.nodl.yaml',
        './fragments/foo.nodl.yaml',
        '../shared/base.nodl.yaml',
        '../base.nodl.yaml',
    ],
)
def test_includes_ref_valid_formats(ref):
    validate({'nodl_version': 2, 'includes': [{'ref': ref}]})


@pytest.mark.parametrize(
    'ref',
    [
        'potato',
        'http://example.com/foo.yaml',
        '/absolute/path.nodl.yaml',
        'nodl:/missing_slash/x',
        'nodl://pkg',
        'nodl://pkg/',
        '',
    ],
)
def test_includes_ref_invalid_formats(ref):
    with pytest.raises(ValidationError):
        validate({'nodl_version': 2, 'includes': [{'ref': ref}]})


# ---------------------------------------------------------------------------
# load_nodl
# ---------------------------------------------------------------------------


def test_load_nodl_from_yaml_file(tmp_path):
    f = tmp_path / 'doc.nodl.yaml'
    f.write_text(
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: /t\n'
        '    type: std_msgs/msg/String\n'
        '    qos:\n'
        '      history: SYSTEM_DEFAULT\n'
        '      reliability: SYSTEM_DEFAULT\n'
    )
    doc = load_nodl(f)
    assert isinstance(doc, NodlDocument)
    assert doc.publishers[0].name == '/t'


def test_load_nodl_from_json_file(tmp_path):
    data = {
        'nodl_version': 2,
        'publishers': [{'name': '/t', 'type': 'std_msgs/msg/String', 'qos': _MIN_QOS}],
    }
    f = tmp_path / 'doc.nodl.yaml'
    f.write_text(json.dumps(data))
    doc = load_nodl(f)
    assert doc.publishers[0].name == '/t'


def test_load_nodl_with_parameters(tmp_path):
    f = tmp_path / 'doc.nodl.yaml'
    f.write_text('nodl_version: 2\nparameters:\n  p:\n    type: string\n')
    doc = load_nodl(f)
    assert 'p' in doc.parameters


def test_load_nodl_invalid_raises(tmp_path):
    f = tmp_path / 'doc.nodl.yaml'
    f.write_text('nodl_version: 2\nparameters:\n  p:\n    type: bad_type\n')
    with pytest.raises(ValidationError):
        load_nodl(f)


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


# ---------------------------------------------------------------------------
# load_nodl() resolves relative includes
# ---------------------------------------------------------------------------

_PUB_A = {
    'name': '/topic_a',
    'type': 'std_msgs/msg/String',
    'qos': _MIN_QOS,
}
_PUB_B = {
    'name': '/topic_b',
    'type': 'geometry_msgs/msg/Twist',
    'qos': _MIN_QOS,
}
_SUB_A = {
    'name': '/sub_a',
    'type': 'sensor_msgs/msg/Image',
    'qos': _MIN_QOS,
}
_SRV_SERVER = {'name': '/set_bool', 'type': 'std_srvs/srv/SetBool'}
_SRV_CLIENT = {'name': '/trigger', 'type': 'std_srvs/srv/Trigger'}
_ACT_SERVER = {'name': '/navigate', 'type': 'nav2_msgs/action/NavigateToPose'}
_ACT_CLIENT = {'name': '/spin', 'type': 'nav2_msgs/action/Spin'}
_PARAM_SPEED = {'type': 'double', 'default_value': 1.0}


def _write_yaml(path, data):
    """Write a dict as YAML to *path*, creating parent dirs."""
    import yaml as _yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_yaml.dump(data, default_flow_style=False), encoding='utf-8')


def test_load_nodl_resolves_relative_include(tmp_path):
    """A file including ./fragment.nodl.yaml merges the fragment's publishers."""
    _write_yaml(
        tmp_path / 'fragment.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [_PUB_A],
        },
    )
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': './fragment.nodl.yaml'}],
        },
    )
    doc = load_nodl(main_file)
    assert any(p.name == '/topic_a' for p in doc.publishers)


def test_load_nodl_relative_include_merges_all_sections(tmp_path):
    """Parameters, publishers, subscriptions, service and action endpoints all merge."""
    _write_yaml(
        tmp_path / 'fragment.nodl.yaml',
        {
            'nodl_version': 2,
            'parameters': {'speed': _PARAM_SPEED},
            'publishers': [_PUB_A],
            'subscriptions': [_SUB_A],
            'service_servers': [_SRV_SERVER],
            'service_clients': [_SRV_CLIENT],
            'action_servers': [_ACT_SERVER],
            'action_clients': [_ACT_CLIENT],
        },
    )
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': './fragment.nodl.yaml'}],
        },
    )
    doc = load_nodl(main_file)
    assert 'speed' in doc.parameters
    assert any(p.name == '/topic_a' for p in doc.publishers)
    assert any(s.name == '/sub_a' for s in doc.subscriptions)
    assert any(s.name == '/set_bool' for s in doc.service_servers)
    assert any(s.name == '/trigger' for s in doc.service_clients)
    assert any(a.name == '/navigate' for a in doc.action_servers)
    assert any(a.name == '/spin' for a in doc.action_clients)


def test_load_nodl_local_declaration_wins_over_include(tmp_path):
    """Same-name topic declared locally and in include → local declaration wins."""
    _write_yaml(
        tmp_path / 'fragment.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [
                {
                    'name': '/topic_a',
                    'type': 'geometry_msgs/msg/Twist',
                    'qos': _MIN_QOS,
                }
            ],
        },
    )
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': './fragment.nodl.yaml'}],
            'publishers': [
                {
                    'name': '/topic_a',
                    'type': 'std_msgs/msg/String',
                    'qos': _MIN_QOS,
                }
            ],
        },
    )
    doc = load_nodl(main_file)
    pubs = [p for p in doc.publishers if p.name == '/topic_a']
    assert len(pubs) == 1
    assert pubs[0].type == 'std_msgs/msg/String'


def test_load_nodl_diamond_deduplication(tmp_path):
    """A→B, A→C, B→D, C→D: D's interface appears exactly once."""
    _write_yaml(
        tmp_path / 'd.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [_PUB_A],
        },
    )
    _write_yaml(
        tmp_path / 'b.nodl.yaml',
        {
            'nodl_version': 2,
            'includes': [{'ref': './d.nodl.yaml'}],
        },
    )
    _write_yaml(
        tmp_path / 'c.nodl.yaml',
        {
            'nodl_version': 2,
            'includes': [{'ref': './d.nodl.yaml'}],
        },
    )
    main_file = tmp_path / 'a.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': './b.nodl.yaml'},
                {'ref': './c.nodl.yaml'},
            ],
        },
    )
    doc = load_nodl(main_file)
    pubs = [p for p in doc.publishers if p.name == '/topic_a']
    assert len(pubs) == 1


def test_load_nodl_merge_identical_ok(tmp_path):
    """Two includes declare same topic identically → deduplicated silently."""
    _write_yaml(
        tmp_path / 'frag1.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [_PUB_A],
        },
    )
    _write_yaml(
        tmp_path / 'frag2.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [_PUB_A],
        },
    )
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': './frag1.nodl.yaml'},
                {'ref': './frag2.nodl.yaml'},
            ],
        },
    )
    doc = load_nodl(main_file)
    pubs = [p for p in doc.publishers if p.name == '/topic_a']
    assert len(pubs) == 1


def test_load_nodl_merge_conflict_error(tmp_path):
    """Two includes declare same topic with different type → error."""
    _write_yaml(
        tmp_path / 'frag1.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [
                {
                    'name': '/topic_a',
                    'type': 'std_msgs/msg/String',
                    'qos': _MIN_QOS,
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / 'frag2.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [
                {
                    'name': '/topic_a',
                    'type': 'geometry_msgs/msg/Twist',
                    'qos': _MIN_QOS,
                }
            ],
        },
    )
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': './frag1.nodl.yaml'},
                {'ref': './frag2.nodl.yaml'},
            ],
        },
    )
    with pytest.raises(Exception, match='topic_a'):
        load_nodl(main_file)


# ---------------------------------------------------------------------------
# Merge-if-identical across all section types
# ---------------------------------------------------------------------------


def test_merge_identical_subscriptions_ok(tmp_path):
    """Two includes declare same subscription identically → deduplicated."""
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'subscriptions': [_SUB_A]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'subscriptions': [_SUB_A]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    doc = load_nodl(main)
    assert len([s for s in doc.subscriptions if s.name == '/sub_a']) == 1


def test_merge_identical_service_servers_ok(tmp_path):
    """Two includes declare same service server identically → deduplicated."""
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'service_servers': [_SRV_SERVER]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'service_servers': [_SRV_SERVER]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    doc = load_nodl(main)
    assert len([s for s in doc.service_servers if s.name == '/set_bool']) == 1


def test_merge_identical_service_clients_ok(tmp_path):
    """Two includes declare same service client identically → deduplicated."""
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'service_clients': [_SRV_CLIENT]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'service_clients': [_SRV_CLIENT]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    doc = load_nodl(main)
    assert len([s for s in doc.service_clients if s.name == '/trigger']) == 1


def test_merge_identical_action_servers_ok(tmp_path):
    """Two includes declare same action server identically → deduplicated."""
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'action_servers': [_ACT_SERVER]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'action_servers': [_ACT_SERVER]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    doc = load_nodl(main)
    assert len([a for a in doc.action_servers if a.name == '/navigate']) == 1


def test_merge_identical_action_clients_ok(tmp_path):
    """Two includes declare same action client identically → deduplicated."""
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'action_clients': [_ACT_CLIENT]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'action_clients': [_ACT_CLIENT]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    doc = load_nodl(main)
    assert len([a for a in doc.action_clients if a.name == '/spin']) == 1


def test_merge_identical_parameters_ok(tmp_path):
    """Two includes declare same parameter identically → deduplicated."""
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'parameters': {'speed': _PARAM_SPEED}})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'parameters': {'speed': _PARAM_SPEED}})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    doc = load_nodl(main)
    assert 'speed' in doc.parameters


# ---------------------------------------------------------------------------
# Merge-conflict across all section types
# ---------------------------------------------------------------------------


def test_merge_conflict_subscriptions(tmp_path):
    """Two includes declare same subscription with different type → error."""
    sub_v1 = {'name': '/sub_a', 'type': 'sensor_msgs/msg/Image', 'qos': _MIN_QOS}
    sub_v2 = {'name': '/sub_a', 'type': 'sensor_msgs/msg/Imu', 'qos': _MIN_QOS}
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'subscriptions': [sub_v1]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'subscriptions': [sub_v2]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='sub_a'):
        load_nodl(main)


def test_merge_conflict_service_servers(tmp_path):
    """Two includes declare same service server with different type → error."""
    srv_v1 = {'name': '/set_bool', 'type': 'std_srvs/srv/SetBool'}
    srv_v2 = {'name': '/set_bool', 'type': 'std_srvs/srv/Trigger'}
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'service_servers': [srv_v1]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'service_servers': [srv_v2]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='set_bool'):
        load_nodl(main)


def test_merge_conflict_service_clients(tmp_path):
    """Two includes declare same service client with different type → error."""
    cli_v1 = {'name': '/trigger', 'type': 'std_srvs/srv/Trigger'}
    cli_v2 = {'name': '/trigger', 'type': 'std_srvs/srv/SetBool'}
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'service_clients': [cli_v1]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'service_clients': [cli_v2]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='trigger'):
        load_nodl(main)


def test_merge_conflict_action_servers(tmp_path):
    """Two includes declare same action server with different type → error."""
    act_v1 = {'name': '/navigate', 'type': 'nav2_msgs/action/NavigateToPose'}
    act_v2 = {'name': '/navigate', 'type': 'nav2_msgs/action/Spin'}
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'action_servers': [act_v1]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'action_servers': [act_v2]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='navigate'):
        load_nodl(main)


def test_merge_conflict_action_clients(tmp_path):
    """Two includes declare same action client with different type → error."""
    act_v1 = {'name': '/spin', 'type': 'nav2_msgs/action/Spin'}
    act_v2 = {'name': '/spin', 'type': 'nav2_msgs/action/NavigateToPose'}
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'action_clients': [act_v1]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'action_clients': [act_v2]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='spin'):
        load_nodl(main)


def test_merge_conflict_parameters(tmp_path):
    """Two includes declare same parameter with different definition → error."""
    param_v1 = {'type': 'double', 'default_value': 1.0}
    param_v2 = {'type': 'double', 'default_value': 99.0}
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'parameters': {'speed': param_v1}})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'parameters': {'speed': param_v2}})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='speed'):
        load_nodl(main)


def test_merge_conflict_parameters_different_type(tmp_path):
    """Two includes declare same parameter with different type → error."""
    param_v1 = {'type': 'double', 'default_value': 1.0}
    param_v2 = {'type': 'int', 'default_value': 1}
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'parameters': {'speed': param_v1}})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'parameters': {'speed': param_v2}})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='speed'):
        load_nodl(main)


# ---------------------------------------------------------------------------
# Conflict on QoS difference (same name, same type, different QoS)
# ---------------------------------------------------------------------------


def test_merge_conflict_publisher_qos_difference(tmp_path):
    """Same-name, same-type publisher with different QoS → error."""
    pub_reliable = {
        'name': '/topic_a',
        'type': 'std_msgs/msg/String',
        'qos': {'history': 'KEEP_LAST', 'depth': 1, 'reliability': 'RELIABLE'},
    }
    pub_best_effort = {
        'name': '/topic_a',
        'type': 'std_msgs/msg/String',
        'qos': {'history': 'KEEP_LAST', 'depth': 1, 'reliability': 'BEST_EFFORT'},
    }
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'publishers': [pub_reliable]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'publishers': [pub_best_effort]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='topic_a'):
        load_nodl(main)


def test_merge_conflict_publisher_depth_difference(tmp_path):
    """Same-name, same-type publisher with different queue depth → error."""
    pub_d1 = {
        'name': '/topic_a',
        'type': 'std_msgs/msg/String',
        'qos': {'history': 'KEEP_LAST', 'depth': 1, 'reliability': 'RELIABLE'},
    }
    pub_d10 = {
        'name': '/topic_a',
        'type': 'std_msgs/msg/String',
        'qos': {'history': 'KEEP_LAST', 'depth': 10, 'reliability': 'RELIABLE'},
    }
    _write_yaml(tmp_path / 'f1.nodl.yaml', {'nodl_version': 2, 'publishers': [pub_d1]})
    _write_yaml(tmp_path / 'f2.nodl.yaml', {'nodl_version': 2, 'publishers': [pub_d10]})
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './f1.nodl.yaml'}, {'ref': './f2.nodl.yaml'}],
        },
    )
    with pytest.raises(Exception, match='topic_a'):
        load_nodl(main)


# ---------------------------------------------------------------------------
# Local-wins for parameters
# ---------------------------------------------------------------------------


def test_local_parameter_wins_over_include(tmp_path):
    """Same-name parameter declared locally and in include → local wins."""
    _write_yaml(
        tmp_path / 'fragment.nodl.yaml',
        {
            'nodl_version': 2,
            'parameters': {'speed': {'type': 'double', 'default_value': 99.0}},
        },
    )
    main = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main,
        {
            'nodl_version': 2,
            'includes': [{'ref': './fragment.nodl.yaml'}],
            'parameters': {'speed': {'type': 'double', 'default_value': 1.0}},
        },
    )
    doc = load_nodl(main)
    assert doc.parameters['speed'].default_value == 1.0


def test_load_nodl_includes_stripped_from_result(tmp_path):
    """Merged NodlDocument has no includes field."""
    _write_yaml(
        tmp_path / 'fragment.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [_PUB_A],
        },
    )
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': './fragment.nodl.yaml'}],
        },
    )
    doc = load_nodl(main_file)
    assert doc.includes is None or doc.includes == []


def test_load_nodl_nested_relative_includes(tmp_path):
    """A includes B, B includes C → C's interface appears in A."""
    sub = tmp_path / 'sub'
    sub.mkdir()
    _write_yaml(
        sub / 'c.nodl.yaml',
        {
            'nodl_version': 2,
            'publishers': [_PUB_A],
        },
    )
    _write_yaml(
        tmp_path / 'b.nodl.yaml',
        {
            'nodl_version': 2,
            'includes': [{'ref': './sub/c.nodl.yaml'}],
        },
    )
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': './b.nodl.yaml'}],
        },
    )
    doc = load_nodl(main_file)
    assert any(p.name == '/topic_a' for p in doc.publishers)


def test_load_nodl_circular_include_handled(tmp_path):
    """A includes B, B includes A → terminates gracefully."""
    _write_yaml(
        tmp_path / 'a.nodl.yaml',
        {
            'nodl_version': 2,
            'includes': [{'ref': './b.nodl.yaml'}],
            'publishers': [_PUB_A],
        },
    )
    _write_yaml(
        tmp_path / 'b.nodl.yaml',
        {
            'nodl_version': 2,
            'includes': [{'ref': './a.nodl.yaml'}],
            'publishers': [_PUB_B],
        },
    )
    main_file = tmp_path / 'a.nodl.yaml'
    doc = load_nodl(main_file)
    # Should have both publishers and not loop forever
    names = {p.name for p in doc.publishers}
    assert '/topic_a' in names
    assert '/topic_b' in names
