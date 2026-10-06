# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Build-time generation of the combined site's CMake API page.

The ``@public`` commands documented in each package's CMake files are rendered by ``cmake_reference``
and collected into ``_generated/cmake/index.rst`` (gitignored, like the other staged content), one section per package.
The page is built only by the combined site, so the per-package ``doc/`` trees stay buildable by ``rosdoc2`` without the CMake domain.
"""

import shutil
from collections.abc import Iterable
from pathlib import Path

from cmake_reference import render_cmake_reference

_HERE = Path(__file__).parent
_REPO = _HERE / '..' / '..'
CMAKE_DST = _HERE / '_generated' / 'cmake'

# Packages that ship public CMake commands, in the order they appear on the page.
PACKAGES = [
    'ament_nodl',
    'nodl_generator_cpp',
    'nodl_generator_py',
]

# Locations of CMake files relative to a package root.
CMAKE_GLOBS = ['cmake/*.cmake', '*-extras.cmake', '*-extras.cmake.in']

_TITLE = 'CMake API'
_INTRO = (
    'Public CMake commands provided by the NoDL packages.\n'
    'Each is generated from the comment header above its definition in the package source.\n'
)


def render_section(package: str, rendered_files: Iterable[str]) -> str:
    """Return a reStructuredText section titled ``package`` holding the non-empty ``rendered_files``.

    Raises ``ValueError`` when ``rendered_files`` has no content, since a listed package is expected to document commands.
    """
    body = '\n'.join(text for text in rendered_files if text)
    if not body:
        raise ValueError(f'{package} has no public CMake commands')
    return f'{package}\n{"-" * len(package)}\n\n{body}'


def render_page(sections: Iterable[str]) -> str:
    """Return the whole CMake API page from package ``sections``."""
    return '\n'.join([_TITLE, '=' * len(_TITLE), '', _INTRO, '.. highlight:: cmake', '', *sections])


def find_cmake_files(package_dir: Path) -> list[Path]:
    """Return the CMake files of ``package_dir`` that may define commands, in a stable order."""
    return sorted({path for pattern in CMAKE_GLOBS for path in package_dir.glob(pattern)})


def generate_cmake_api_docs() -> None:
    """Write ``_generated/cmake/index.rst`` from the ``@public`` commands of ``PACKAGES``.

    Raises ``ValueError`` if a listed package has no public commands.
    """
    sections = [
        render_section(
            package,
            (render_cmake_reference(path.read_text(encoding='utf-8')) for path in find_cmake_files(_REPO / package)),
        )
        for package in PACKAGES
    ]
    if CMAKE_DST.exists():
        shutil.rmtree(CMAKE_DST)
    CMAKE_DST.mkdir(parents=True)
    (CMAKE_DST / 'index.rst').write_text(render_page(sections))
