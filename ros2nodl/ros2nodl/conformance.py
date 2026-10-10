# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runtime orchestration for NoDL conformance checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from nodl_schema import Difference, DiffReport, IgnoreRule, diff_report, load_nodl

IGNORE_ENVIRONMENT_VARIABLE = 'NODL_CONFORMANCE_IGNORE'


def ignore_from_environment(environ: Mapping[str, str]) -> list[str]:
    """Return the whitespace-separated ignore rules in ``NODL_CONFORMANCE_IGNORE``.

    For the command line and generated tests to apply an environment-wide default.
    The checks in this module take their rules as arguments only.
    """
    return environ.get(IGNORE_ENVIRONMENT_VARIABLE, '').split()


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


def conformance_report(
    *,
    nodl_file: str,
    node_fqn: str,
    timeout_sec: float = 15.0,
    ignore: Iterable[IgnoreRule | str] = (),
) -> DiffReport:
    """Compare one running node with one explicit NoDL document.

    ``ignore`` rules leave observed entities that the document does not declare out of the differences,
    and list them in ``ignored``.
    See :class:`nodl_schema.IgnoreRule` for the rule syntax.
    """
    from ros2nodl.infrastructure import strip_infrastructure

    rules = [rule if isinstance(rule, IgnoreRule) else IgnoreRule.parse(rule) for rule in ignore]
    expected = strip_infrastructure(_load_document(nodl_file))

    from ros2nodl.describe import DescribeOptions, describe_node

    result = describe_node(
        node_fqn,
        timeout_sec=timeout_sec,
        options=DescribeOptions(include_parameters=True, keep_hidden=False),
    )
    report = diff_report(expected, result.doc, node_fqn=node_fqn, ignore=rules)
    differences = [_gap_difference(gap) for gap in result.gaps]
    differences.extend(report.differences)
    return DiffReport(sorted(differences, key=_sort_key), report.ignored)


def check_conformance(
    *,
    nodl_file: str,
    node_fqn: str,
    timeout_sec: float = 15.0,
    ignore: Iterable[IgnoreRule | str] = (),
) -> list[Difference]:
    """Return the conformance differences of :func:`conformance_report`."""
    return conformance_report(
        nodl_file=nodl_file,
        node_fqn=node_fqn,
        timeout_sec=timeout_sec,
        ignore=ignore,
    ).differences


def assert_conforms(
    *,
    nodl_file: str,
    node_fqn: str,
    timeout_sec: float = 15.0,
    ignore: Iterable[IgnoreRule | str] = (),
) -> DiffReport:
    """Raise one assertion that contains every conformance difference.

    Returns the report on success, so callers can show what ``ignore`` left out.
    """
    report = conformance_report(
        nodl_file=nodl_file,
        node_fqn=node_fqn,
        timeout_sec=timeout_sec,
        ignore=ignore,
    )
    if report.differences:
        rendered = '\n'.join(f'  {difference}' for difference in report.differences)
        message = f'NoDL conformance failed for {node_fqn!r}:\n{rendered}'
        if report.ignored:
            message += '\n' + format_ignored(report)
        raise AssertionError(message)
    return report


def format_ignored(report: DiffReport) -> str:
    """Render the entities that ignore rules left out, one per line."""
    return '\n'.join(f'  ignored {difference}' for difference in report.ignored)
