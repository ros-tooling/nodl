# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ament-style CMake comment parser, on inline CMake text."""

from textwrap import dedent

from cmake_reference import CMakeCommand, parse_cmake_commands, render_cmake_reference

LICENSE = """\
# Copyright 2026 Example, Inc.
#
# Licensed under the Apache License, Version 2.0.

"""


def test_public_function_is_documented():
    text = dedent("""\
        # Do the thing.
        #
        # :param target: the target name.
        # :type target: string
        #
        # @public
        #
        function(do_thing target)
        endfunction()
    """)
    assert parse_cmake_commands(text) == [
        CMakeCommand(
            name='do_thing',
            args=('target',),
            body=('Do the thing.', '', ':param target: the target name.', ':type target: string'),
        )
    ]


def test_private_and_unmarked_commands_are_skipped():
    text = dedent("""\
        # Internal.
        #
        # @private
        function(_hidden)
        endfunction()

        # Documented but not marked public.
        function(unmarked)
        endfunction()
    """)
    assert parse_cmake_commands(text) == []


def test_license_header_is_not_a_doc_block():
    text = LICENSE + 'macro(undocumented)\nendmacro()\n'
    assert parse_cmake_commands(text) == []


def test_blank_line_separates_license_from_doc_block():
    text = LICENSE + '# Docs.\n#\n# @public\nmacro(documented)\nendmacro()\n'
    assert [c.body for c in parse_cmake_commands(text)] == [('Docs.',)]


def test_one_blank_line_between_block_and_definition_is_allowed():
    text = '# Docs.\n#\n# @public\n\nmacro(spaced)\nendmacro()\n'
    assert [c.name for c in parse_cmake_commands(text)] == ['spaced']


def test_two_blank_lines_between_block_and_definition_end_the_block():
    text = '# Docs.\n#\n# @public\n\n\nmacro(far)\nendmacro()\n'
    assert parse_cmake_commands(text) == []


def test_macro_and_function_in_one_file_keep_file_order():
    text = '# A\n# @public\nmacro(first)\nendmacro()\n\n# B\n# @public\nfunction(second a b)\nendfunction()\n'
    commands = parse_cmake_commands(text)
    assert [(c.name, c.args) for c in commands] == [('first', ()), ('second', ('a', 'b'))]


def test_keywords_are_case_insensitive_and_preserve_name_case():
    text = '# Docs.\n# @public\nFUNCTION(Mixed_Case arg)\nENDFUNCTION()\n'
    assert [c.name for c in parse_cmake_commands(text)] == ['Mixed_Case']


def test_definition_arguments_may_span_lines():
    text = '# Docs.\n# @public\nfunction(multi\n  one\n  two)\nendfunction()\n'
    assert parse_cmake_commands(text)[0].args == ('one', 'two')


def test_definition_without_comment_is_skipped():
    assert parse_cmake_commands('function(bare)\nendfunction()\n') == []


def test_comment_prefix_is_stripped_and_indentation_kept():
    text = '# :param X: first line\n#   continued\n#\n# @public\nfunction(f X)\nendfunction()\n'
    assert parse_cmake_commands(text)[0].body == (':param X: first line', '  continued')


def test_deprecated_marker_is_recorded_and_removed_from_body():
    text = '# Old.\n#\n# @public\n# @deprecated\nmacro(old)\nendmacro()\n'
    (command,) = parse_cmake_commands(text)
    assert command.deprecated == ''
    assert command.body == ('Old.',)


def test_deprecated_marker_may_carry_a_version():
    text = '# Old.\n# @public\n# @deprecated 2.1\nmacro(old)\nendmacro()\n'
    assert parse_cmake_commands(text)[0].deprecated == '2.1'


def test_render_emits_directive_with_usage_and_indented_body():
    text = '# Do it.\n#\n# :param X: the x.\n#   More.\n# :type X: string\n#\n# @public\nfunction(do_it X)\nendfunction()\n'
    assert render_cmake_reference(text) == dedent("""\
        .. cmake:command:: do_it

           .. code-block:: cmake

              do_it(X)

           Do it.

           :param X: the x.
             More.
           :type X: string
    """)


def test_usage_marks_keyword_arguments_when_params_are_not_positional():
    text = (
        '# Docs.\n# :param target: positional.\n# :param FILE: keyword.\n# @public\nfunction(f target)\nendfunction()\n'
    )
    assert '   f(target [<keyword arguments>...])\n' in render_cmake_reference(text)


def test_usage_has_no_keyword_marker_when_all_params_are_positional():
    text = '# Docs.\n# :param a: A.\n# :param b: B.\n# @public\nfunction(f a b)\nendfunction()\n'
    assert '   f(a b)\n' in render_cmake_reference(text)


def test_usage_marks_keyword_arguments_for_keyword_fields():
    text = '# Docs.\n# :keyword NAME: the name.\n# @public\nmacro(f)\nendmacro()\n'
    assert '   f([<keyword arguments>...])\n' in render_cmake_reference(text)


def test_form_feed_in_a_comment_does_not_shift_later_definitions():
    text = '# Page\x0cbreak.\n# @public\nmacro(first)\nendmacro()\n\x0b\n# B\n# @public\nmacro(second)\nendmacro()\n'
    assert [c.name for c in parse_cmake_commands(text)] == ['first', 'second']


def test_crlf_line_endings():
    text = (
        '# Docs.\r\n# @public\r\nmacro(first)\r\nendmacro()\r\n\r\n# B\r\n# @public\r\nmacro(second)\r\nendmacro()\r\n'
    )
    commands = parse_cmake_commands(text)
    assert [(c.name, c.body) for c in commands] == [('first', ('Docs.',)), ('second', ('B',))]


def test_lone_cr_line_endings():
    text = '# Docs.\r# @public\rmacro(first)\rendmacro()\r'
    assert [c.name for c in parse_cmake_commands(text)] == ['first']


def test_render_deprecated_without_text_is_a_warning():
    text = '# Old.\n# @public\n# @deprecated\nmacro(old)\nendmacro()\n'
    rendered = render_cmake_reference(text)
    assert '   .. warning::\n\n      This command is deprecated.\n' in rendered
    assert '@' not in rendered


def test_render_deprecated_with_version_uses_deprecated_directive():
    text = '# Old.\n# @public\n# @deprecated 2.1.0\nmacro(old)\nendmacro()\n'
    assert '   .. deprecated:: 2.1.0\n' in render_cmake_reference(text)


def test_render_deprecated_with_prose_is_a_warning_that_includes_it():
    text = '# Old.\n# @public\n# @deprecated after Jazzy\nmacro(old)\nendmacro()\n'
    rendered = render_cmake_reference(text)
    assert '   .. warning::\n\n      This command is deprecated: after Jazzy\n' in rendered
    assert '.. deprecated::' not in rendered


def test_render_separates_commands_and_is_empty_without_public_commands():
    text = '# A\n# @public\nmacro(a)\nendmacro()\n# B\n# @public\nmacro(b)\nendmacro()\n'
    rendered = render_cmake_reference(text)
    assert rendered.count('.. cmake:command::') == 2
    assert '\n\n.. cmake:command:: b' in rendered
    assert render_cmake_reference('set(X 1)\n') == ''
