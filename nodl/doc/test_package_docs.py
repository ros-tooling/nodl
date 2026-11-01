# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the package.xml-derived package list in package_docs."""

import pytest
from package_docs import _REPO, PACKAGES, package_description


def _package_xml(tmp_path, description_element):
    path = tmp_path / 'package.xml'
    path.write_text(f'<package format="3"><name>pkg</name>{description_element}</package>')
    return path


def test_description_collapses_whitespace_across_lines(tmp_path):
    path = _package_xml(tmp_path, '<description>\n  First sentence.\n\n  Second   sentence.\n</description>')
    assert package_description(path) == 'First sentence. Second sentence.'


@pytest.mark.parametrize('element', ['', '<description/>', '<description>\n  \n</description>'])
def test_missing_or_empty_description_raises(tmp_path, element):
    with pytest.raises(ValueError, match='has no <description> text'):
        package_description(_package_xml(tmp_path, element))


def test_missing_package_xml_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match='has no package.xml'):
        package_description(tmp_path / 'package.xml')


@pytest.mark.parametrize('pkg', PACKAGES)
def test_every_documented_package_has_a_package_xml_description(pkg):
    assert package_description(_REPO / pkg / 'package.xml')
