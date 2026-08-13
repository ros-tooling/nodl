# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for nodl_generator_cpp tests."""

from pathlib import Path

import pytest

from nodl_schema import dump_nodl, resolver_registered
from nodl_schema.models import NodlDocument

INCLUDES_DIR = Path(__file__).parent / '_includes'


class FakeResolver:
    """
    Resolves ``test://<name>`` references from in-memory or on-disk nodl files.

    Follows the same pattern as nodl_schema's test_composition.FakeResolver.
    Supports three registration methods:

    - ``add(name, doc)`` — register a :class:`NodlDocument` model (serialised to YAML).
    - ``add_text(name, text)`` — register raw YAML text (for deliberately malformed documents).
    - ``add_file(name, path)`` — register the contents of a file on disk.
    """

    scheme = 'test://'

    def __init__(self) -> None:
        self.docs: dict[str, str] = {}
        self.calls: list[str] = []

    def add(self, name: str, doc: NodlDocument) -> str:
        """Register *doc* as ``test://<name>`` and return the ref."""
        return self.add_text(name, dump_nodl(doc))

    def add_text(self, name: str, text: str) -> str:
        """Register raw YAML/JSON text as ``test://<name>``."""
        ref = f'{self.scheme}{name}'
        self.docs[ref] = text
        return ref

    def add_file(self, name: str, path: Path) -> str:
        """Register the contents of *path* as ``test://<name>``."""
        return self.add_text(name, path.read_text())

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
    """A FakeResolver pre-loaded with every ``_includes/*.nodl.yaml``.

    Registered for the duration of one test, then removed.
    """
    resolver = FakeResolver()
    for nodl_file in sorted(INCLUDES_DIR.glob('*.nodl.yaml')):
        name = nodl_file.name.removesuffix('.nodl.yaml')
        resolver.add_file(name, nodl_file)

    with resolver_registered(resolver):
        yield resolver
