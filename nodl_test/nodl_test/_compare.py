"""Compare two NodlDocuments and report differences."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from nodl.models import NodlDocument, Parameter, QoS, ServiceEndpoint, TopicEndpoint


@dataclass
class Difference:
    kind: str           # 'missing' | 'extra' | 'type_mismatch' | 'qos_mismatch'
    section: str        # 'publisher' | 'subscription' | 'service_server' | 'service_client' | 'parameter'
    name: str
    detail: str

    def __str__(self) -> str:
        return f'[{self.kind}] {self.section} {self.name!r}: {self.detail}'


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def _expand_tilde(name: str, node_fqn: Optional[str]) -> str:
    """Expand a leading ~ to the node's fully-qualified name.

    '~/foo' with node_fqn='/ns/node' → '/ns/node/foo'
    Names without ~ are returned unchanged.
    node_fqn=None means no expansion is performed.
    """
    if not name.startswith('~') or node_fqn is None:
        return name
    return node_fqn.rstrip('/') + '/' + name[2:]


def _normalize_names(
    endpoints: list,
    name_attr: str,
    node_fqn: Optional[str],
) -> dict:
    """Return a dict keyed by expanded name."""
    result = {}
    for ep in endpoints:
        raw = getattr(ep, name_attr)
        key = _expand_tilde(raw, node_fqn)
        result[key] = ep
    return result


# ---------------------------------------------------------------------------
# QoS comparison
# ---------------------------------------------------------------------------

def _qos_matches(expected: Optional[QoS], actual: Optional[QoS]) -> tuple[bool, str]:
    """Return (ok, reason). reason is empty string when ok is True.

    Rules:
      - expected is None  → not specified in NoDL, skip comparison → ok
      - actual is None    → introspection could not determine (SYSTEM_DEFAULT /
                            BEST_AVAILABLE); treat as wildcard → ok
      - both present      → compare reliability, history, durability field by field
    """
    if expected is None or actual is None:
        return True, ''

    if expected.reliability != actual.reliability:
        return False, (
            f'reliability: expected {expected.reliability}, got {actual.reliability}'
        )

    if expected.history != actual.history:
        return False, (
            f'history: expected {expected.history}, got {actual.history}'
        )

    if expected.durability is not None and actual.durability is not None:
        if expected.durability != actual.durability:
            return False, (
                f'durability: expected {expected.durability}, got {actual.durability}'
            )

    return True, ''


# ---------------------------------------------------------------------------
# Section comparators
# ---------------------------------------------------------------------------

def _compare_topics(
    expected: List[TopicEndpoint],
    actual: List[TopicEndpoint],
    section: str,
    node_fqn: Optional[str] = None,
) -> List[Difference]:
    diffs: List[Difference] = []
    exp_map = _normalize_names(expected, 'topic', node_fqn)
    act_map = {a.topic: a for a in actual}

    for name, exp in exp_map.items():
        if name not in act_map:
            diffs.append(Difference('missing', section, name, 'not found on running node'))
            continue
        act = act_map[name]
        if exp.type != act.type:
            diffs.append(Difference(
                'type_mismatch', section, name,
                f'expected {exp.type!r}, got {act.type!r}',
            ))
            continue
        ok, reason = _qos_matches(exp.qos, act.qos)
        if not ok:
            diffs.append(Difference('qos_mismatch', section, name, reason))

    for name in act_map:
        if name not in exp_map:
            diffs.append(Difference('extra', section, name, 'present on node but not in NoDL spec'))

    return diffs


def _compare_services(
    expected: List[ServiceEndpoint],
    actual: List[ServiceEndpoint],
    section: str,
    node_fqn: Optional[str] = None,
) -> List[Difference]:
    diffs: List[Difference] = []
    exp_map = _normalize_names(expected, 'name', node_fqn)
    act_map = {a.name: a for a in actual}

    for name, exp in exp_map.items():
        if name not in act_map:
            diffs.append(Difference('missing', section, name, 'not found on running node'))
        elif exp.type != act_map[name].type:
            diffs.append(Difference(
                'type_mismatch', section, name,
                f'expected {exp.type!r}, got {act_map[name].type!r}',
            ))

    for name in act_map:
        if name not in exp_map:
            diffs.append(Difference('extra', section, name, 'present on node but not in NoDL spec'))

    return diffs


def _compare_parameters(
    expected: Dict[str, Parameter],
    actual: Dict[str, Parameter],
) -> List[Difference]:
    diffs: List[Difference] = []

    for name, exp in expected.items():
        if name not in actual:
            diffs.append(Difference('missing', 'parameter', name, 'not declared on running node'))
        elif exp.type != actual[name].type:
            diffs.append(Difference(
                'type_mismatch', 'parameter', name,
                f'expected {exp.type!r}, got {actual[name].type!r}',
            ))

    for name in actual:
        if name not in expected:
            diffs.append(Difference('extra', 'parameter', name, 'declared on node but not in NoDL spec'))

    return diffs


# ---------------------------------------------------------------------------
# Top-level comparison
# ---------------------------------------------------------------------------

def compare(
    expected: NodlDocument,
    actual: NodlDocument,
    node_fqn: Optional[str] = None,
) -> List[Difference]:
    """Return all differences between the expected NoDL spec and the described node.

    node_fqn: fully-qualified node name (e.g. '/ns/my_node'), used to expand
        '~' prefixes in expected names from built-in/fragment documents.
    """
    diffs: List[Difference] = []
    diffs += _compare_topics(
        expected.publishers or [], actual.publishers or [], 'publisher', node_fqn
    )
    diffs += _compare_topics(
        expected.subscriptions or [], actual.subscriptions or [], 'subscription', node_fqn
    )
    diffs += _compare_services(
        expected.service_servers or [], actual.service_servers or [], 'service_server', node_fqn
    )
    diffs += _compare_services(
        expected.service_clients or [], actual.service_clients or [], 'service_client', node_fqn
    )
    diffs += _compare_parameters(
        expected.parameters or {}, actual.parameters or {}
    )
    return diffs
