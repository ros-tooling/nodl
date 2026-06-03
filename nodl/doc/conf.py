# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the NoDL project documentation."""

import os
import re
from pathlib import Path

import yaml

project = 'NoDL'
copyright = '2026, Open Source Robotics Foundation, Inc.'
author = 'NoDL contributors'

# Status banner; bump once the project stabilizes.
html_title = 'NoDL (v2, in development)'

extensions = [
    'myst_parser',
    'sphinx_immaterial',
    'sphinx_immaterial.apidoc.json.domain',
    'sphinx.ext.extlinks',
]

# -- Schema sources ----------------------------------------------------------
# The canonical schemas live in the nodl_schema package. The immaterial JSON
# domain only discovers files beneath this docs source dir, so mirror them into
# _generated/ at build time.
#
# The mirrored copies are also rewritten for presentation (see _docs_id below):
# the canonical schemas identify themselves and cross-reference one another with
# fully-qualified raw.githubusercontent.com URLs pinned to `main`. Rendered
# verbatim those are both noisy ("array of https://.../nodl.schema.yaml#/...")
# and wrong for PR/branch builds, which document a different ref than `main`.
# We replace every `$id`/`$ref` in the copies with short, branch-agnostic names
# so the rendered reference reads "array of TopicEndpoint" and links resolve to
# documented sections on the same page. The canonical schemas (and the URLs real
# consumers resolve) are untouched; only the docs copies change.
_DOC_DIR = Path(__file__).parent.resolve()
_SCHEMA_SRC = _DOC_DIR / '..' / '..' / 'nodl_schema' / 'nodl_schema' / 'schemas'
_SCHEMA_DST = _DOC_DIR / '_generated' / 'schemas'
_SCHEMA_DST.mkdir(parents=True, exist_ok=True)

# Short display id for a schema or `#/definitions/<name>` definition key.
# `topic_endpoint`/`qosProfile` -> `TopicEndpoint`/`QosProfile`.
_REF_DEFINITION_RE = re.compile(r'#/definitions/(?P<name>\w+)$')


def _docs_id(name: str) -> str:
    return ''.join(part[:1].upper() + part[1:] for part in name.split('_'))


def _rewrite_schema_refs(node, ref_map: dict) -> None:
    """Rewrite every `$ref` in-place to its short id, recursively."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == '$ref' and isinstance(value, str):
                match = _REF_DEFINITION_RE.search(value)
                if match:
                    node[key] = ref_map[match.group('name')]
            else:
                _rewrite_schema_refs(value, ref_map)
    elif isinstance(node, list):
        for item in node:
            _rewrite_schema_refs(item, ref_map)


_docs_schemas = {p.name: yaml.safe_load(p.read_text()) for p in _SCHEMA_SRC.glob('*.schema.yaml')}
# Definition names are unique across both files, so one global map suffices and
# also resolves the cross-file ref (nodl's parameters -> parameter.schema.yaml).
_ref_map = {name: _docs_id(name) for doc in _docs_schemas.values() for name in doc.get('definitions', {})}
for _filename, _doc in _docs_schemas.items():
    # Drop the ".schema.yaml" suffix for the top-level id (nodl.schema.yaml -> Nodl).
    _doc['$id'] = _docs_id(_filename.split('.')[0])
    for _name, _definition in _doc.get('definitions', {}).items():
        _definition['$id'] = _ref_map[_name]
    _rewrite_schema_refs(_doc, _ref_map)
    (_SCHEMA_DST / _filename).write_text(yaml.safe_dump(_doc, sort_keys=False, allow_unicode=True))

    # Emit an RST snippet with one `.. json:schema::` directive per definition, in
    # source order, so schema.md can `.. include::` it instead of hand-listing every
    # type. New definitions then appear in the docs automatically. Written as .txt
    # so Sphinx doesn't treat it as a standalone source document.
    _directives = '\n'.join(f'.. json:schema:: {_ref_map[name]}' for name in _doc.get('definitions', {}))
    (_SCHEMA_DST / f'{_filename.split(".")[0]}_definitions.txt').write_text(_directives + '\n')

# Patterns are relative to this source dir; the domain skips anything in
# exclude_patterns, so _generated/ is intentionally left out of those.
json_schemas = ['_generated/schemas/*.yaml']
json_schema_validate = True

# -- GitHub source links -----------------------------------------------------
if os.environ.get('READTHEDOCS_VERSION_TYPE') == 'external':
    # For PR builds RTD sets it to the PR number, which is not a valid GitHub ref, so we substitute the commit SHA instead.
    _repo_ref = os.environ.get('READTHEDOCS_GIT_COMMIT_HASH', 'main')
else:
    # For branch/tag builds (including local/GitHub Actions), this is the readable ref name.
    _repo_ref = os.environ.get('READTHEDOCS_GIT_IDENTIFIER', 'main')

extlinks = {
    'repo': (f'https://github.com/ros-tooling/nodl/blob/{_repo_ref}/%s', '%s'),
}

myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'fieldlist',
    'tasklist',
]

source_suffix = {
    '.md': 'markdown',
    '.rst': 'restructuredtext',
}

# -- HTML output (sphinx-immaterial) -----------------------------------------
html_theme = 'sphinx_immaterial'
html_theme_options = {
    'icon': {'repo': 'fontawesome/brands/github'},
    'repo_url': 'https://github.com/ros-tooling/nodl',
    'repo_name': 'ros-tooling/nodl',
    'edit_uri': f'blob/{_repo_ref}/nodl/doc',
    'features': [
        'navigation.expand',
        'navigation.top',
        'toc.follow',
        'search.highlight',
        'search.share',
        'content.code.copy',
    ],
    'palette': [
        {
            'media': '(prefers-color-scheme: light)',
            'scheme': 'default',
            'primary': 'blue',
            'accent': 'light-blue',
            'toggle': {
                'icon': 'material/lightbulb-outline',
                'name': 'Switch to dark mode',
            },
        },
        {
            'media': '(prefers-color-scheme: dark)',
            'scheme': 'slate',
            'primary': 'blue',
            'accent': 'light-blue',
            'toggle': {
                'icon': 'material/lightbulb',
                'name': 'Switch to light mode',
            },
        },
    ],
}

exclude_patterns = ['_build', '.venv', 'Thumbs.db', '.DS_Store']
