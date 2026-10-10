# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Rules that select observed entities to leave out of a semantic diff."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase

_SECTION_BY_KIND = {
    'publisher': 'publishers',
    'subscription': 'subscriptions',
    'service_server': 'service_servers',
    'service_client': 'service_clients',
    'action_server': 'action_servers',
    'action_client': 'action_clients',
    'parameter': 'parameters',
}

IGNORE_KINDS = tuple(_SECTION_BY_KIND)


@dataclass(frozen=True)
class IgnoreRule:
    """Selects entities by kind, name pattern, and optionally type pattern.

    ``kind`` is one of :data:`IGNORE_KINDS`.
    ``name`` is an :func:`fnmatch.fnmatchcase` glob over the fully qualified entity name,
    where ``*`` also matches ``/``.
    A parameter rule matches the parameter name as declared.
    ``type`` is an optional glob over the full ``package/kind/Name`` type, and does not apply to parameters.

    The text form is ``KIND:NAME`` or ``KIND:NAME:TYPE``, for example
    ``publisher:/debug/*`` or ``subscription:/robot/*:std_msgs/msg/String``.
    """

    kind: str
    name: str
    type: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _SECTION_BY_KIND:
            raise ValueError(f'ignore kind must be one of {", ".join(IGNORE_KINDS)}, got {self.kind!r}')
        if not self.name:
            raise ValueError('ignore name pattern must not be empty')
        if self.kind != 'parameter' and not self.name.startswith(('/', '*')):
            raise ValueError(
                f'ignore name pattern must be fully qualified, starting with "/" or "*", got {self.name!r}'
            )
        if self.type is not None and (self.kind == 'parameter' or not self.type):
            raise ValueError(f'ignore type pattern is not valid for {self}')

    @property
    def section(self) -> str:
        """Name of the document section this rule selects from."""
        return _SECTION_BY_KIND[self.kind]

    @classmethod
    def parse(cls, text: str) -> IgnoreRule:
        """Parse the ``KIND:NAME[:TYPE]`` text form."""
        kind, separator, rest = text.partition(':')
        if not separator:
            raise ValueError(f'ignore rule must look like KIND:NAME[:TYPE], got {text!r}')
        name, separator, type_pattern = rest.partition(':')
        return cls(kind=kind, name=name, type=type_pattern if separator else None)

    def matches(self, section: str, name: str, type_name: str | None = None) -> bool:
        """Return whether this rule selects an entity of ``section`` called ``name``."""
        if section != self.section or not fnmatchcase(name, self.name):
            return False
        return self.type is None or (type_name is not None and fnmatchcase(type_name, self.type))

    def __str__(self) -> str:
        return ':'.join(part for part in (self.kind, self.name, self.type) if part is not None)


def coerce_rules(rules) -> list[IgnoreRule]:
    """Return ``rules`` as :class:`IgnoreRule` objects, parsing any strings."""
    return [rule if isinstance(rule, IgnoreRule) else IgnoreRule.parse(rule) for rule in rules]
