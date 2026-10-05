# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Render ament-style CMake comment headers as reStructuredText for the ``cmake:command`` domain.

ament_cmake documents a macro with a ``#`` comment block directly above its ``function(`` or ``macro(`` definition.
A blank line ends the block, which keeps a license header out of it, with one exception described in ``_comment_block_above``.
The block holds Sphinx field lists (``:param X:``, ``:type X:``) and an ``@public`` marker for public API.
The output leaves the field lists as they are, so the Sphinx project must give ``cmake:command`` typed fields.

This module is a pure text-to-text transform with no Sphinx or filesystem dependency.
Not supported: ``#[[ ]]`` bracket comments, comments inside an argument list, and ``##`` comment prefixes.
"""

import re
from dataclasses import dataclass

# A definition may be indented and may span lines, e.g. ``function(name\n  arg)``.
_DEFINITION = re.compile(
    r'^[ \t]*(?:function|macro)[ \t]*\([ \t]*(?P<name>[^\s()]+)(?P<args>[^)]*)\)',
    re.IGNORECASE | re.MULTILINE,
)
_FIELD_NAME = re.compile(r'^:(?:param|keyword)[ \t]+(?P<name>[^:\s]+):')
_MARKER = re.compile(r'^@(?P<marker>public|private|deprecated)\b[ \t]*(?P<rest>.*)$')
_VERSION = re.compile(r'^\d[\w.]*$')
_KEYWORD_ARGUMENTS = '[<keyword arguments>...]'


@dataclass(frozen=True)
class CMakeCommand:
    """A documented CMake command.

    ``body`` is the comment text with markers and the comment prefix removed.
    ``deprecated`` is ``None`` when not deprecated, otherwise the text after ``@deprecated`` (possibly empty).
    """

    name: str
    args: tuple[str, ...]
    body: tuple[str, ...]
    deprecated: str | None = None


def _comment_block_above(lines: list[str], index: int) -> list[str]:
    """Return the ``#`` comment lines directly above ``lines[index]``, with the comment prefix removed.

    One blank line may separate the block from the definition, as in ament_auto_package.
    A blank line above the block ends it, so a license header stays out.
    """
    end = index - 1 if index > 0 and not lines[index - 1].strip() else index
    start = end
    while start > 0 and lines[start - 1].lstrip().startswith('#'):
        start -= 1
    block = [line.lstrip()[1:] for line in lines[start:end]]
    return [line[1:] if line.startswith(' ') else line for line in block]


def _trim_blank(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start]:
        start += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return lines[start:end]


def parse_cmake_commands(text: str) -> list[CMakeCommand]:
    """Return the public commands documented in the CMake file ``text``, in file order."""
    # Only ``\n`` separates lines, so line numbers agree with match offsets (``str.splitlines`` also splits on ``\x0c`` etc.).
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    commands = []
    for match in _DEFINITION.finditer(text):
        body = []
        public = False
        deprecated = None
        for line in _comment_block_above(lines, text.count('\n', 0, match.start())):
            marker = _MARKER.match(line.strip())
            if marker is None:
                body.append(line.rstrip())
            elif marker['marker'] == 'public':
                public = True
            elif marker['marker'] == 'deprecated':
                deprecated = marker['rest'].strip()
        if public:
            commands.append(
                CMakeCommand(
                    name=match['name'],
                    args=tuple(match['args'].split()),
                    body=tuple(_trim_blank(body)),
                    deprecated=deprecated,
                )
            )
    return commands


def _usage(command: CMakeCommand) -> str:
    """Return the usage line, marking keyword arguments when the body documents names beyond the positional ones."""
    documented = (m['name'] for line in command.body if (m := _FIELD_NAME.match(line)))
    args = list(command.args)
    if any(name not in command.args for name in documented):
        args.append(_KEYWORD_ARGUMENTS)
    return f'{command.name}({" ".join(args)})'


def _deprecation(text: str) -> list[str]:
    """Return the admonition for ``@deprecated``: a ``deprecated`` directive for a version, else a warning."""
    if _VERSION.match(text):
        return [f'.. deprecated:: {text}', '']
    message = f'This command is deprecated: {text}' if text else 'This command is deprecated.'
    return ['.. warning::', '', f'   {message}', '']


def render_command(command: CMakeCommand) -> str:
    """Render one command as a ``cmake:command`` directive.

    The domain's ``cmake:command`` takes only a name, so the usage is shown in a ``cmake`` code block.
    """
    content = ['.. code-block:: cmake', '', f'   {_usage(command)}', '']
    if command.deprecated is not None:
        content += _deprecation(command.deprecated)
    content += command.body
    indented = [f'   {line}' if line else '' for line in content]
    return '\n'.join([f'.. cmake:command:: {command.name}', '', *indented]).rstrip() + '\n'


def render_cmake_reference(text: str) -> str:
    """Return reStructuredText for the public commands in the CMake file ``text``.

    The result is empty when the file documents no public commands.
    """
    return '\n'.join(render_command(command) for command in parse_cmake_commands(text))
