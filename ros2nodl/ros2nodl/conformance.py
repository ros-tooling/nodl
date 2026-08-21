# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runtime orchestration for NoDL conformance checks."""

from __future__ import annotations

from pathlib import Path

from nodl_conformance import Difference, diff
from nodl_schema import load_nodl


def _load_document(nodl_file: str):
    path = Path(nodl_file)
    try:
        return load_nodl(path)
    except Exception as exc:
        raise ValueError(f'failed to load NoDL document {str(path)!r}: {exc}') from exc


def _gap_difference(gap) -> Difference:
    section = gap.path.split('[', 1)[0].split('.', 1)[0]
    return Difference(
        kind='unverifiable',
        section=section,
        name=gap.path,
        detail=gap.reason,
    )


def _sort_key(difference: Difference) -> tuple[str, str, str, str]:
    return difference.section, difference.name, difference.kind, difference.detail


def check_conformance(
    *,
    nodl_file: str,
    node_fqn: str,
    timeout_sec: float = 15.0,
) -> list[Difference]:
    """Compare one running node with one explicit NoDL document."""
    expected = _load_document(nodl_file)

    from ros2nodl.describe import DescribeOptions, describe_node

    result = describe_node(
        node_fqn,
        timeout_sec=timeout_sec,
        options=DescribeOptions(include_parameters=True, keep_hidden=False),
    )
    differences = [_gap_difference(gap) for gap in result.gaps]
    differences.extend(diff(expected, result.doc, node_fqn=node_fqn))
    return sorted(differences, key=_sort_key)


def assert_conforms(
    *,
    nodl_file: str,
    node_fqn: str,
    timeout_sec: float = 15.0,
) -> None:
    """Raise one assertion that contains every conformance difference."""
    differences = check_conformance(
        nodl_file=nodl_file,
        node_fqn=node_fqn,
        timeout_sec=timeout_sec,
    )
    if differences:
        rendered = '\n'.join(f'  {difference}' for difference in differences)
        raise AssertionError(f'NoDL conformance failed for {node_fqn!r}:\n{rendered}')
