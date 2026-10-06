# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Helpers for the optional include prefix that scopes generated headers."""

from __future__ import annotations

import re

_SEGMENT_RE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*')


def validate_include_prefix(include_prefix: str | None) -> None:
    """Validate that *include_prefix* is ``None`` or a ``/``-separated list of safe path segments.

    The prefix is a directory path and an ``#include`` string, so it need not be a C++ identifier.
    Each segment must start with a letter, digit, or underscore, and continue with letters, digits, ``_``, ``.``, or ``-``.
    Raises :class:`ValueError` for an empty prefix, empty segments (leading, trailing, or doubled slashes),
    backslashes, and the segments ``.`` and ``..``.

    >>> validate_include_prefix(None)
    >>> validate_include_prefix('my_package')
    >>> validate_include_prefix('my-package/detail')
    >>> validate_include_prefix('../my_package')
    Traceback (most recent call last):
    ...
    ValueError: include_prefix must be one or more '/'-separated path segments, got '../my_package'
    """
    if include_prefix is None:
        return
    segments = include_prefix.split('/')
    if not all(_SEGMENT_RE.fullmatch(segment) and segment not in ('.', '..') for segment in segments):
        raise ValueError(f"include_prefix must be one or more '/'-separated path segments, got {include_prefix!r}")


def prefixed(include_prefix: str | None, filename: str) -> str:
    """Return *filename* placed under *include_prefix*, or unchanged when the prefix is ``None``.

    >>> prefixed(None, 'my_node.hpp')
    'my_node.hpp'
    >>> prefixed('my_package', 'my_node.hpp')
    'my_package/my_node.hpp'
    """
    return filename if include_prefix is None else f'{include_prefix}/{filename}'
