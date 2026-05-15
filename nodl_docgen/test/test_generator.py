"""Unit tests for the RST generator."""
import pytest

from nodl.models import NodlDocument, NodeMetadata, Parameter, QoS, TopicEndpoint, ServiceEndpoint
from nodl_docgen._generator import _qos_str, generate_rst


# ---------------------------------------------------------------------------
# _qos_str
# ---------------------------------------------------------------------------

def test_qos_str_none():
    assert _qos_str(None) == 'default'


def test_qos_str_reliable():
    assert _qos_str(QoS(history=10, reliability='RELIABLE')) == 'Reliable · depth 10'


def test_qos_str_best_effort():
    assert _qos_str(QoS(history=5, reliability='BEST_EFFORT')) == 'Best effort · depth 5'


def test_qos_str_keep_all():
    assert _qos_str(QoS(history='ALL', reliability='RELIABLE')) == 'Reliable · keep all'


def test_qos_str_transient_local():
    result = _qos_str(QoS(history=10, reliability='RELIABLE', durability='TRANSIENT_LOCAL'))
    assert result == 'Reliable · depth 10 · transient local'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FULL_DOC = NodlDocument(
    node=NodeMetadata(name='my_node'),
    parameters={
        'rate': Parameter(type='double', default_value=10.0, description='Publish rate in Hz'),
        'frame_id': Parameter(type='string', default_value='base_link'),
        'enabled': Parameter(type='bool', default_value=True, read_only=True),
    },
    publishers=[
        TopicEndpoint(
            topic='/scan',
            type='sensor_msgs/msg/LaserScan',
            qos=QoS(history=10, reliability='RELIABLE'),
        ),
    ],
    subscriptions=[
        TopicEndpoint(topic='/cmd', type='std_msgs/msg/String'),
    ],
    service_servers=[
        ServiceEndpoint(name='/reset', type='std_srvs/srv/Trigger', description='Reset the node'),
    ],
    service_clients=[
        ServiceEndpoint(name='/set_mode', type='std_srvs/srv/SetBool'),
    ],
)

_MINIMAL_DOC = NodlDocument(node=NodeMetadata(name='bare_node'))


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def test_title_is_node_name():
    rst = generate_rst(_FULL_DOC)
    assert 'my_node\n=======' in rst


def test_title_underline_matches_length():
    doc = NodlDocument(node=NodeMetadata(name='a_longer_name'))
    rst = generate_rst(doc)
    assert 'a_longer_name\n=============' in rst


def test_fallback_title_when_no_node():
    rst = generate_rst(NodlDocument())
    assert rst.startswith('node\n====')


# ---------------------------------------------------------------------------
# Publishers
# ---------------------------------------------------------------------------

def test_publishers_section_present():
    rst = generate_rst(_FULL_DOC)
    assert 'Publishers\n----------' in rst


def test_publishers_topic_in_output():
    rst = generate_rst(_FULL_DOC)
    assert '``/scan``' in rst


def test_publishers_type_in_output():
    rst = generate_rst(_FULL_DOC)
    assert '``sensor_msgs/msg/LaserScan``' in rst


def test_publishers_qos_in_output():
    rst = generate_rst(_FULL_DOC)
    assert 'Reliable · depth 10' in rst


def test_no_publishers_section_when_empty():
    rst = generate_rst(_MINIMAL_DOC)
    assert 'Publishers' not in rst


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def test_subscriptions_section_present():
    rst = generate_rst(_FULL_DOC)
    assert 'Subscriptions\n-------------' in rst


def test_subscriptions_default_qos_label():
    rst = generate_rst(_FULL_DOC)
    # /cmd has no QoS spec
    assert 'default' in rst


def test_no_subscriptions_section_when_empty():
    rst = generate_rst(_MINIMAL_DOC)
    assert 'Subscriptions' not in rst


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

def test_parameters_section_present():
    rst = generate_rst(_FULL_DOC)
    assert 'Parameters\n----------' in rst


def test_parameter_name_in_output():
    rst = generate_rst(_FULL_DOC)
    assert '``rate``' in rst


def test_parameter_type_in_output():
    rst = generate_rst(_FULL_DOC)
    assert '``double``' in rst


def test_parameter_default_in_output():
    rst = generate_rst(_FULL_DOC)
    assert '``10.0``' in rst


def test_parameter_description_in_output():
    rst = generate_rst(_FULL_DOC)
    assert 'Publish rate in Hz' in rst


def test_read_only_annotation():
    rst = generate_rst(_FULL_DOC)
    assert '*(read-only)*' in rst


def test_no_parameters_section_when_empty():
    rst = generate_rst(_MINIMAL_DOC)
    assert 'Parameters' not in rst


# ---------------------------------------------------------------------------
# Service servers / clients
# ---------------------------------------------------------------------------

def test_service_server_section_present():
    rst = generate_rst(_FULL_DOC)
    assert 'Service Servers\n---------------' in rst


def test_service_server_name_in_output():
    rst = generate_rst(_FULL_DOC)
    assert '``/reset``' in rst


def test_service_server_description_in_output():
    rst = generate_rst(_FULL_DOC)
    assert 'Reset the node' in rst


def test_service_client_section_present():
    rst = generate_rst(_FULL_DOC)
    assert 'Service Clients\n---------------' in rst


def test_service_client_name_in_output():
    rst = generate_rst(_FULL_DOC)
    assert '``/set_mode``' in rst


# ---------------------------------------------------------------------------
# list-table structure
# ---------------------------------------------------------------------------

def test_list_table_directive_present():
    rst = generate_rst(_FULL_DOC)
    assert '.. list-table::' in rst


def test_list_table_header_rows():
    rst = generate_rst(_FULL_DOC)
    assert ':header-rows: 1' in rst


def test_list_table_widths_present():
    rst = generate_rst(_FULL_DOC)
    assert ':widths:' in rst
