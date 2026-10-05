# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure page assembly in cmake_api_docs."""

import pytest
from cmake_api_docs import render_page, render_section


def test_section_is_titled_and_joins_non_empty_files():
    assert render_section('pkg', ['a\n', '', 'b\n']) == 'pkg\n---\n\na\n\nb\n'


def test_section_without_commands_raises():
    with pytest.raises(ValueError, match='pkg has no public CMake commands'):
        render_section('pkg', ['', ''])


def test_page_has_title_highlight_and_sections():
    page = render_page(['one\n---\n\nx\n'])
    assert page.startswith('CMake API\n=========\n')
    assert '.. highlight:: cmake' in page
    assert page.endswith('one\n---\n\nx\n')
