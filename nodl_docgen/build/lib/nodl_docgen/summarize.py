# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Presentation-neutral summaries of a NoDL document.

A :class:`NodeSummary` is the rendering-ready form of a document:
a description, the refs it includes, and one table of plain-string rows per interface category.
Every formatting decision lives here, so a renderer only has to lay out text it is handed:
QoS profiles collapse to one line, parameter validators become constraint sentences,
and values are written as YAML literals.

Nothing in this module knows about Sphinx, docutils, or markdown,
which keeps it usable from a REPL, a CLI, or a test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

import yaml

from nodl_schema.composition import merge_documents
from nodl_schema.loader import DocumentTree
from nodl_schema.models import (
    ActionEndpoint,
    History,
    NodlDocument,
    ParameterDefinition,
    QosProfile,
    ServiceEndpoint,
    TopicEndpoint,
    Validation,
)

# --------------------------------
# Rows and summary
# --------------------------------


@dataclass(frozen=True)
class ParameterRow:
    """One declared ROS parameter.

    ``default`` is empty when the document declares no default, which makes the parameter required at startup.
    ``read_only`` is ``'yes'`` or empty, so it can be dropped into a table cell as-is.
    """

    name: str
    type: str
    default: str = ''
    description: str = ''
    read_only: str = ''
    constraints: tuple[str, ...] = ()
    additional_constraints: str = ''


@dataclass(frozen=True)
class EndpointRow:
    """One topic or service endpoint.

    ``qos`` is empty when the profile is absent or entirely system default.
    """

    name: str
    type: str
    qos: str = ''
    description: str = ''


@dataclass(frozen=True)
class ActionRow:
    """One action endpoint. Actions carry no QoS profile in NoDL."""

    name: str
    type: str
    description: str = ''


@dataclass(frozen=True)
class NodeSummary:
    """Everything a renderer needs to draw one node's interface.

    ``includes`` holds the direct include refs, unresolved, for a "composed from" note.
    Every other field is a table whose rows are in document order.
    """

    description: str = ''
    includes: tuple[str, ...] = ()
    parameters: tuple[ParameterRow, ...] = ()
    publishers: tuple[EndpointRow, ...] = ()
    subscriptions: tuple[EndpointRow, ...] = ()
    service_servers: tuple[EndpointRow, ...] = ()
    service_clients: tuple[EndpointRow, ...] = ()
    action_servers: tuple[ActionRow, ...] = ()
    action_clients: tuple[ActionRow, ...] = ()


# --------------------------------
# Values
# --------------------------------


def format_value(value: Any) -> str:
    """Render ``value`` as the YAML literal an author would write in a parameter file.

    This keeps types legible without inventing a second notation:
    ``true`` rather than ``True``, ``[a, b]`` rather than ``['a', 'b']``, and quotes only where YAML needs them.

    A dumped scalar is a whole YAML document, so the trailing ``...`` document end marker is stripped.
    A value whose own text ends in dots survives that:
    the marker is always on its own line, and a bare ``...`` is quoted by the dumper.
    """
    text = yaml.safe_dump(value, default_flow_style=True, width=10**6).strip()
    return text.removesuffix('...').strip()


def _text(value: str | None) -> str:
    """Normalize optional prose to a stripped string, since a missing description and an empty one read the same."""
    return (value or '').strip()


def _type_name(value: Any) -> str:
    """The declared type as written in the document, whether the model parsed it to an enum or left it a string."""
    return value.value if isinstance(value, Enum) else str(value)


# --------------------------------
# QoS
# --------------------------------

_SYSTEM_DEFAULT = 'SYSTEM_DEFAULT'
_DURATION_UNITS = (('s', 1_000_000_000), ('ms', 1_000_000), ('us', 1_000))


def _format_duration(nanoseconds: int) -> str:
    """The duration in the largest unit that divides it exactly, so round numbers stay round."""
    for suffix, scale in _DURATION_UNITS:
        if nanoseconds % scale == 0:
            return f'{nanoseconds // scale}{suffix}'
    return f'{nanoseconds}ns'


def _duration_part(label: str, nanoseconds: int | None) -> str:
    """A labelled duration, or nothing when it is absent or zero.

    Zero means "not enforced" for every duration in a QoS profile, which is what happens by default anyway.
    """
    if not nanoseconds:
        return ''
    return f'{label} {_format_duration(nanoseconds)}'


def _policy_part(policy: Enum | None) -> str:
    """A policy name, or nothing when it is absent or the system default."""
    if policy is None or policy.value == _SYSTEM_DEFAULT:
        return ''
    return str(policy.value)


def _history_part(qos: QosProfile) -> str:
    """History with its queue depth, since the two are read together."""
    history = '' if qos.history is History.SYSTEM_DEFAULT else str(qos.history.value)
    if qos.depth is None:
        return history
    return f'{history}({qos.depth})' if history else f'depth {qos.depth}'


def format_qos(qos: QosProfile | None) -> str:
    """Compress a QoS profile to one readable line, naming only what differs from the system default.

    Returns the empty string for an absent or entirely default profile,
    so a table cell stays quiet when the author expressed no preference.
    """
    if qos is None:
        return ''

    parts = (
        _history_part(qos),
        _policy_part(qos.reliability),
        _policy_part(qos.durability),
        _duration_part('deadline', qos.deadline_ns),
        _duration_part('lifespan', qos.lifespan_ns),
        _policy_part(qos.liveliness),
        _duration_part('liveliness lease', qos.liveliness_lease_duration_ns),
    )
    return ', '.join(part for part in parts if part)


# --------------------------------
# Parameter validators
# --------------------------------

# Sentence per validator, in the order sentences are emitted: value, then size, then per-element constraints.
# Adapted from ``generate_parameter_library``'s markdown conventions,
# reworded so every sentence has the parameter as its implied subject and can be read as a bullet.
_CONSTRAINT_SENTENCES: dict[str, str] = {
    'bounds': 'must be within bounds VALUES',
    'lt': 'must be less than VALUES',
    'lt_eq': 'must be less than or equal to VALUES',
    'gt': 'must be greater than VALUES',
    'gt_eq': 'must be greater than or equal to VALUES',
    'one_of': 'must be one of VALUES',
    'not_empty': 'must not be empty',
    'fixed_size': 'length must be VALUES',
    'size_gt': 'length must be greater than VALUES',
    'size_lt': 'length must be less than VALUES',
    'element_bounds': 'every element must be within bounds VALUES',
    'lower_element_bounds': 'every element must be greater than or equal to VALUES',
    'upper_element_bounds': 'every element must be less than or equal to VALUES',
    'subset_of': 'every element must be one of VALUES',
    'unique': 'must contain no duplicates',
}


def _format_arguments(arguments: Any) -> str:
    """Render validator arguments, unwrapping the single-element list that single-argument validators are written as.

    ``fixed_size: [6]`` and ``fixed_size: 6`` mean the same thing and read the same,
    and ``one_of: [[a, b]]`` is about its inner list.
    """
    if arguments is None:
        return ''
    if isinstance(arguments, list):
        if not arguments:
            return ''
        if len(arguments) == 1:
            arguments = arguments[0]
    return format_value(arguments)


def _constraint_sentence(name: str, arguments: Any) -> str:
    """One validator as a sentence, falling back to naming an unrecognized validator rather than dropping it."""
    values = _format_arguments(arguments)
    template = _CONSTRAINT_SENTENCES.get(name)
    if template is None:
        return f'custom validator {name}' + (f' with {values}' if values else '')
    if 'VALUES' in template:
        return template.replace('VALUES', values)
    return template


def constraint_sentences(validation: Validation | None) -> tuple[str, ...]:
    """Render a parameter's validators as constraint sentences.

    The ``name`` and ``name<>`` spellings of a validator are the same validator, and read identically.
    Sentences come out in a fixed order rather than the order they were authored in,
    because the parsed document does not retain the authored order.
    """
    if validation is None:
        return ()

    authored = {
        name.removesuffix('<>'): arguments
        for name, arguments in validation.dict(by_alias=True, exclude_unset=True).items()
    }
    known = [name for name in _CONSTRAINT_SENTENCES if name in authored]
    # Custom, namespace-qualified validators sort by name; the schema allows them even though the model cannot hold them yet.
    unknown = sorted(authored.keys() - _CONSTRAINT_SENTENCES.keys())

    return tuple(_constraint_sentence(name, authored[name]) for name in known + unknown)


# --------------------------------
# Rows from models
# --------------------------------

_MAP_KEY = re.compile(r'__map_(\w+)')


def parameter_display_name(name: str) -> str:
    """The parameter name as a reader should see it, with ``__map_<key>`` segments shown as ``<key>``.

    A mapped parameter stands for one parameter per runtime key,
    so a placeholder describes it better than the raw spelling does.
    """
    return _MAP_KEY.sub(r'<\1>', name)


def summarize_parameter(name: str, parameter: ParameterDefinition) -> ParameterRow:
    """One parameter definition as a row."""
    has_default = 'default_value' in parameter.__fields_set__
    return ParameterRow(
        name=parameter_display_name(name),
        type=_type_name(parameter.type),
        default=format_value(parameter.default_value) if has_default else '',
        description=_text(parameter.description),
        read_only='yes' if parameter.read_only else '',
        constraints=constraint_sentences(parameter.validation),
        additional_constraints=_text(parameter.additional_constraints),
    )


def summarize_endpoint(endpoint: TopicEndpoint | ServiceEndpoint) -> EndpointRow:
    """One topic or service endpoint as a row."""
    return EndpointRow(
        name=endpoint.name,
        type=endpoint.type,
        qos=format_qos(endpoint.qos),
        description=_text(endpoint.description),
    )


def summarize_action(endpoint: ActionEndpoint) -> ActionRow:
    """One action endpoint as a row."""
    return ActionRow(name=endpoint.name, type=endpoint.type, description=_text(endpoint.description))


# --------------------------------
# Documents
# --------------------------------


def summarize_document(doc: NodlDocument) -> NodeSummary:
    """Summarize one document, as authored, reporting its own unresolved ``include`` refs."""
    return NodeSummary(
        description=_text(doc.description),
        includes=tuple(reference.ref for reference in (doc.include or [])),
        parameters=tuple(summarize_parameter(name, p) for name, p in (doc.parameters or {}).items()),
        publishers=tuple(summarize_endpoint(e) for e in (doc.publishers or [])),
        subscriptions=tuple(summarize_endpoint(e) for e in (doc.subscriptions or [])),
        service_servers=tuple(summarize_endpoint(e) for e in (doc.service_servers or [])),
        service_clients=tuple(summarize_endpoint(e) for e in (doc.service_clients or [])),
        action_servers=tuple(summarize_action(e) for e in (doc.action_servers or [])),
        action_clients=tuple(summarize_action(e) for e in (doc.action_clients or [])),
    )


def summarize_tree(tree: DocumentTree) -> NodeSummary:
    """Summarize a resolved document tree as one effective interface.

    Included documents are merged into the root, so the summary is what the node actually exposes.
    Merging drops the ``include`` section, so the root's direct refs are restored afterwards,
    letting a renderer say where the rest of the interface came from.
    """
    summary = summarize_document(merge_documents(tree.flatten()))
    return replace(summary, includes=tuple(included.ref for included in tree.resolved_includes))
