# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Golden tests for the pure summary core.

Each test states a NoDL document (or a single model) and the exact ``NodeSummary`` it must produce,
so a change in rendering shows up as a diff in expected text rather than as a judgement call.
"""

from pathlib import Path

import pytest

from nodl_docgen.summarize import (
    ActionRow,
    EndpointRow,
    NodeSummary,
    ParameterRow,
    constraint_sentences,
    format_qos,
    format_value,
    parameter_display_name,
    summarize_document,
    summarize_tree,
)
from nodl_schema import load_nodl_with_doc_tree, parse_nodl
from nodl_schema.composition import merge_documents
from nodl_schema.models import Durability, History, Liveliness, QosProfile, Reliability, Validation

# --------------------------------
# QoS summaries
# --------------------------------


def _qos(**overrides) -> QosProfile:
    """A QoS profile that is entirely system default, plus whatever the caller sets."""
    fields = {'history': History.SYSTEM_DEFAULT, 'reliability': Reliability.SYSTEM_DEFAULT}
    return QosProfile(**{**fields, **overrides})


def test_qos_all_system_default_is_empty():
    assert format_qos(_qos()) == ''


def test_qos_absent_profile_is_empty():
    # Service endpoints may omit qos entirely.
    assert format_qos(None) == ''


def test_qos_history_carries_its_depth():
    assert format_qos(_qos(history=History.KEEP_LAST, depth=10)) == 'KEEP_LAST(10)'


def test_qos_keep_all_has_no_depth():
    assert format_qos(_qos(history=History.KEEP_ALL)) == 'KEEP_ALL'


def test_qos_depth_without_a_history_policy_stands_alone():
    assert format_qos(_qos(depth=5)) == 'depth 5'


def test_qos_policies_appear_in_profile_order():
    profile = _qos(
        history=History.KEEP_LAST,
        depth=1,
        reliability=Reliability.RELIABLE,
        durability=Durability.TRANSIENT_LOCAL,
        liveliness=Liveliness.MANUAL_BY_TOPIC,
    )
    assert format_qos(profile) == 'KEEP_LAST(1), RELIABLE, TRANSIENT_LOCAL, MANUAL_BY_TOPIC'


def test_qos_best_available_policies_are_not_default():
    profile = _qos(reliability=Reliability.BEST_AVAILABLE, durability=Durability.BEST_AVAILABLE)
    assert format_qos(profile) == 'BEST_AVAILABLE, BEST_AVAILABLE'


def test_qos_system_default_optional_policies_are_omitted():
    profile = _qos(durability=Durability.SYSTEM_DEFAULT, liveliness=Liveliness.SYSTEM_DEFAULT)
    assert format_qos(profile) == ''


def test_qos_durations_are_labelled_and_scaled():
    profile = _qos(deadline_ns=100_000_000, lifespan_ns=2_000_000_000, liveliness_lease_duration_ns=1_500_000)
    assert format_qos(profile) == 'deadline 100ms, lifespan 2s, liveliness lease 1500us'


def test_qos_duration_falls_back_to_nanoseconds():
    assert format_qos(_qos(deadline_ns=1234)) == 'deadline 1234ns'


def test_qos_zero_durations_are_omitted():
    # Zero means "not enforced" for every duration in the profile, which is the default behaviour.
    profile = _qos(deadline_ns=0, lifespan_ns=0, liveliness_lease_duration_ns=0)
    assert format_qos(profile) == ''


# --------------------------------
# Values as YAML literals
# --------------------------------


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (True, 'true'),
        (False, 'false'),
        (0, '0'),
        (1.5, '1.5'),
        ('base_link', 'base_link'),
        ('', "''"),
        ('true', "'true'"),
        ([1, 2, 3], '[1, 2, 3]'),
        (['a', 'b'], '[a, b]'),
        ([], '[]'),
        (None, 'null'),
        (float('inf'), '.inf'),
        # Stripping the YAML document end marker must not eat a value that itself ends in dots.
        ('wait...', 'wait...'),
        ('...', "'...'"),
    ],
)
def test_format_value(value, expected):
    assert format_value(value) == expected


def test_format_value_keeps_long_sequences_on_one_line():
    assert format_value([f'element_{index}' for index in range(12)]).count('\n') == 0


# --------------------------------
# Validator constraint sentences
# --------------------------------


def _sentences(**validation) -> tuple[str, ...]:
    return constraint_sentences(Validation.parse_obj(validation))


def test_no_validation_has_no_sentences():
    assert constraint_sentences(None) == ()
    assert constraint_sentences(Validation.parse_obj({})) == ()


@pytest.mark.parametrize(
    ('validation', 'expected'),
    [
        ({'bounds': [0.0, 1.0]}, 'must be within bounds [0.0, 1.0]'),
        ({'lt': 3}, 'must be less than 3.0'),
        ({'lt_eq': [3.0]}, 'must be less than or equal to 3.0'),
        ({'gt': 0.5}, 'must be greater than 0.5'),
        ({'gt_eq': 0.5}, 'must be greater than or equal to 0.5'),
        ({'one_of': [['spline', 'linear']]}, 'must be one of [spline, linear]'),
        ({'not_empty': None}, 'must not be empty'),
        ({'not_empty': []}, 'must not be empty'),
        ({'fixed_size': 6}, 'length must be 6'),
        ({'size_gt': [2]}, 'length must be greater than 2'),
        ({'size_lt': 8}, 'length must be less than 8'),
        ({'element_bounds': [-1.0, 1.0]}, 'every element must be within bounds [-1.0, 1.0]'),
        ({'lower_element_bounds': 0.0}, 'every element must be greater than or equal to 0.0'),
        ({'upper_element_bounds': 1.0}, 'every element must be less than or equal to 1.0'),
        ({'subset_of': [['x', 'y', 'z']]}, 'every element must be one of [x, y, z]'),
        ({'unique': None}, 'must contain no duplicates'),
    ],
)
def test_one_sentence_per_validator(validation, expected):
    assert _sentences(**validation) == (expected,)


@pytest.mark.parametrize('name', ['bounds', 'bounds<>'])
def test_the_angle_bracket_suffix_is_equivalent(name):
    assert _sentences(**{name: [0.0, 1.0]}) == ('must be within bounds [0.0, 1.0]',)


def test_sentences_are_ordered_canonically_not_as_authored():
    # The parsed model cannot report the order the author wrote the validators in,
    # so a fixed order keeps the output stable.
    validation = {'unique': None, 'element_bounds': [0.0, 1.0], 'size_gt<>': [1]}
    assert _sentences(**validation) == (
        'length must be greater than 1',
        'every element must be within bounds [0.0, 1.0]',
        'must contain no duplicates',
    )


# --------------------------------
# Parameter names
# --------------------------------


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('rate_hz', 'rate_hz'),
        ('limits.max', 'limits.max'),
        ('joints.__map_joint.limits.max', 'joints.<joint>.limits.max'),
        ('__map_a.__map_b', '<a>.<b>'),
    ],
)
def test_parameter_display_name(name, expected):
    assert parameter_display_name(name) == expected


# --------------------------------
# Whole documents
# --------------------------------

EMPTY_DOCUMENT = 'nodl_version: 2\n'

FULL_DOCUMENT = """
nodl_version: 2
description: |
  A driver node.
parameters:
  frame_id:
    type: string
    default_value: base_link
    description: TF frame the scan is published in.
    read_only: true
    validation:
      not_empty:
  rate_hz:
    type: double
    default_value: 20.0
    validation:
      bounds<>: [1.0, 100.0]
  joints.__map_joint.limits:
    type: double_array
    additional_constraints: entries must be monotonic
    validation:
      element_bounds: [-1.0, 1.0]
      unique:
publishers:
  - name: /scan
    type: sensor_msgs/msg/LaserScan
    description: Raw scans.
    qos:
      history: KEEP_LAST
      depth: 5
      reliability: BEST_EFFORT
subscriptions:
  - name: /cmd_vel
    type: geometry_msgs/msg/Twist
    qos:
      history: SYSTEM_DEFAULT
      reliability: SYSTEM_DEFAULT
service_servers:
  - name: ~/reset
    type: std_srvs/srv/Trigger
service_clients:
  - name: /other/reset
    type: std_srvs/srv/Trigger
    qos:
      history: KEEP_ALL
      reliability: RELIABLE
action_servers:
  - name: /navigate
    type: nav2_msgs/action/NavigateToPose
    description: Drive to a pose.
action_clients:
  - name: /dock
    type: nav2_msgs/action/NavigateToPose
"""


def test_empty_document_summarizes_to_empty_sections():
    assert summarize_document(parse_nodl(EMPTY_DOCUMENT)) == NodeSummary()


def test_full_document_golden_summary():
    expected = NodeSummary(
        description='A driver node.',
        includes=(),
        parameters=(
            ParameterRow(
                name='frame_id',
                type='string',
                default='base_link',
                description='TF frame the scan is published in.',
                read_only='yes',
                constraints=('must not be empty',),
                additional_constraints='',
            ),
            ParameterRow(
                name='rate_hz',
                type='double',
                default='20.0',
                description='',
                read_only='',
                constraints=('must be within bounds [1.0, 100.0]',),
                additional_constraints='',
            ),
            ParameterRow(
                name='joints.<joint>.limits',
                type='double_array',
                default='',
                description='',
                read_only='',
                constraints=(
                    'every element must be within bounds [-1.0, 1.0]',
                    'must contain no duplicates',
                ),
                additional_constraints='entries must be monotonic',
            ),
        ),
        publishers=(
            EndpointRow(
                name='/scan',
                type='sensor_msgs/msg/LaserScan',
                qos='KEEP_LAST(5), BEST_EFFORT',
                description='Raw scans.',
            ),
        ),
        subscriptions=(EndpointRow(name='/cmd_vel', type='geometry_msgs/msg/Twist', qos='', description=''),),
        service_servers=(EndpointRow(name='~/reset', type='std_srvs/srv/Trigger', qos='', description=''),),
        service_clients=(
            EndpointRow(name='/other/reset', type='std_srvs/srv/Trigger', qos='KEEP_ALL, RELIABLE', description=''),
        ),
        action_servers=(
            ActionRow(name='/navigate', type='nav2_msgs/action/NavigateToPose', description='Drive to a pose.'),
        ),
        action_clients=(ActionRow(name='/dock', type='nav2_msgs/action/NavigateToPose', description=''),),
    )

    assert summarize_document(parse_nodl(FULL_DOCUMENT)) == expected


def test_a_parameter_without_a_default_is_required():
    doc = parse_nodl('nodl_version: 2\nparameters:\n  needed:\n    type: int\n')
    assert summarize_document(doc).parameters == (
        ParameterRow(
            name='needed',
            type='int',
            default='',
            description='',
            read_only='',
            constraints=(),
            additional_constraints='',
        ),
    )


def test_an_explicit_null_default_is_rendered():
    doc = parse_nodl('nodl_version: 2\nparameters:\n  maybe:\n    type: string\n    default_value: null\n')
    assert summarize_document(doc).parameters[0].default == 'null'


def test_unresolved_includes_are_listed_from_the_document():
    doc = parse_nodl('nodl_version: 2\ninclude:\n  - ref: nodl://sensor_common/imu\n')
    assert summarize_document(doc).includes == ('nodl://sensor_common/imu',)


# --------------------------------
# Resolved document trees
# --------------------------------

ROOT_WITH_INCLUDE = """
nodl_version: 2
description: The composed node.
include:
  - ref: local://shared.nodl.yaml
publishers:
  - name: /own
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 1
      reliability: RELIABLE
"""

SHARED = """
nodl_version: 2
description: Ignored, the root description wins.
parameters:
  shared_rate:
    type: double
    default_value: 1.0
publishers:
  - name: /shared
    type: std_msgs/msg/String
    qos:
      history: SYSTEM_DEFAULT
      reliability: SYSTEM_DEFAULT
"""


def test_resolved_tree_summarizes_the_merged_interface(tmp_path: Path):
    (tmp_path / 'shared.nodl.yaml').write_text(SHARED)
    root = tmp_path / 'root.nodl.yaml'
    root.write_text(ROOT_WITH_INCLUDE)

    _, tree = load_nodl_with_doc_tree(root)
    summary = summarize_tree(tree)

    assert summary.description == 'The composed node.'
    assert summary.includes == ('local://shared.nodl.yaml',)
    assert summary.publishers == (
        EndpointRow(name='/own', type='std_msgs/msg/String', qos='KEEP_LAST(1), RELIABLE', description=''),
        EndpointRow(name='/shared', type='std_msgs/msg/String', qos='', description=''),
    )
    assert summary.parameters == (
        ParameterRow(
            name='shared_rate',
            type='double',
            default='1.0',
            description='',
            read_only='',
            constraints=(),
            additional_constraints='',
        ),
    )


def test_resolved_tree_reports_refs_the_merge_dropped(tmp_path: Path):
    # merge_documents resolves the include away, so the refs can only come from the tree.
    (tmp_path / 'shared.nodl.yaml').write_text(SHARED)
    root = tmp_path / 'root.nodl.yaml'
    root.write_text(ROOT_WITH_INCLUDE)

    _, tree = load_nodl_with_doc_tree(root)

    assert summarize_document(merge_documents(tree.flatten())).includes == ()
    assert summarize_tree(tree).includes == ('local://shared.nodl.yaml',)


def test_resolved_tree_lists_only_direct_includes(tmp_path: Path):
    (tmp_path / 'leaf.nodl.yaml').write_text('nodl_version: 2\n')
    (tmp_path / 'mid.nodl.yaml').write_text('nodl_version: 2\ninclude:\n  - ref: local://leaf.nodl.yaml\n')
    root = tmp_path / 'root.nodl.yaml'
    root.write_text('nodl_version: 2\ninclude:\n  - ref: local://mid.nodl.yaml\n')

    _, tree = load_nodl_with_doc_tree(root)

    assert summarize_tree(tree).includes == ('local://mid.nodl.yaml',)
