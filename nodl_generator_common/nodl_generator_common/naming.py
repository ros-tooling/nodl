# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Language-agnostic name conversions shared by NoDL generators.

Pure string utilities with no ROS or target-language dependencies.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# CamelCase → snake_case
# ---------------------------------------------------------------------------

_CAMEL_RE1 = re.compile(r'([A-Z]+)([A-Z][a-z])')
_CAMEL_RE2 = re.compile(r'([a-z0-9])([A-Z])')


def camel_to_snake(name: str) -> str:
    """Convert a CamelCase name to snake_case.

    >>> camel_to_snake('NavigateToPose')
    'navigate_to_pose'
    >>> camel_to_snake('SetBool')
    'set_bool'
    """
    s = _CAMEL_RE1.sub(r'\1_\2', name)
    return _CAMEL_RE2.sub(r'\1_\2', s).lower()


# ---------------------------------------------------------------------------
# ROS entity name → identifier fragment
# ---------------------------------------------------------------------------


def to_member_name(name: str) -> str:
    """Sanitise a ROS entity name for use as an identifier fragment.

    Strips leading ``~/`` or ``/``, replaces remaining ``/`` with ``_``.

    >>> to_member_name('/rosout')
    'rosout'
    >>> to_member_name('~/describe_parameters')
    'describe_parameters'
    >>> to_member_name('cmd_vel')
    'cmd_vel'
    """
    name = name.removeprefix('~/').lstrip('/')
    return name.replace('/', '_')
