# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for nodl_generator_cpp tests."""

from pathlib import Path

import pytest

from nodl_schema import resolver_registered

GOLDEN_DIR = Path(__file__).parent / 'golden'
INCLUDES_DIR = GOLDEN_DIR / '_includes'


class FakeResolver:
    """Resolves ``test://<name>`` references from on-disk nodl files.

    Follows the same pattern as nodl_schema's test_composition.FakeResolver,
    but loads from the golden/_includes/ directory so the test documents
    are human-readable files rather than inline strings.
    """

    scheme = 'test://'

    def __init__(self) -> None:
        self.docs: dict[str, str] = {}
        self.calls: list[str] = []

    def add_file(self, name: str, path: Path) -> str:
        """Register the contents of *path* as ``test://<name>``."""
        ref = f'{self.scheme}{name}'
        self.docs[ref] = path.read_text()
        return ref

    def handles(self, ref: str) -> bool:
        return ref.startswith(self.scheme)

    def resolve(self, ref: str) -> str:
        self.calls.append(ref)
        try:
            return self.docs[ref]
        except KeyError:
            raise FileNotFoundError(ref)


@pytest.fixture()
def fake_resolver():
    """A FakeResolver pre-loaded with every ``golden/includes/*.nodl.yaml``.

    Registered for the duration of one test, then removed.
    """
    resolver = FakeResolver()
    for nodl_file in sorted(INCLUDES_DIR.glob('*.nodl.yaml')):
        name = nodl_file.name.removesuffix('.nodl.yaml')
        resolver.add_file(name, nodl_file)

    with resolver_registered(resolver):
        yield resolver
