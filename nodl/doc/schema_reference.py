# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Build-time helpers for the JSON-domain schema reference rendered by schema.md.

Two adaptations let the sphinx-immaterial JSON domain present the canonical
nodl_schema schemas well; ``conf.py`` calls both from ``setup()``:

* :func:`mirror_schemas_for_docs` copies the schemas in with display-friendly ids.
* :func:`patch_object_value_type` makes maps show their value type.
"""

import re
from pathlib import Path

import yaml

_HERE = Path(__file__).parent
SCHEMA_SRC = _HERE / '..' / '..' / 'nodl_schema' / 'nodl_schema' / 'schemas'
SCHEMA_DST = _HERE / '_generated' / 'schemas'
# Where the mirrored schemas land, relative to the Sphinx source dir (== _HERE);
# this is the value conf.py feeds to the json_schemas config.
SCHEMA_GLOB = '_generated/schemas/*.yaml'

_DEFINITION_REF = re.compile(r'#/definitions/(?P<name>\w+)$')


def _short_id(name: str) -> str:
    """Display id for a schema/definition: ``topic_endpoint`` -> ``TopicEndpoint``."""
    return ''.join(word[:1].upper() + word[1:] for word in name.split('_'))


def _rewrite_refs(node, ref_map: dict) -> None:
    """Replace every ``#/definitions/<name>`` $ref with its short id, in place."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == '$ref' and isinstance(value, str):
                match = _DEFINITION_REF.search(value)
                if match:
                    node[key] = ref_map[match.group('name')]
            else:
                _rewrite_refs(value, ref_map)
    elif isinstance(node, list):
        for item in node:
            _rewrite_refs(item, ref_map)


def _drop_redundant_keys(node) -> None:
    """Drop the ``<>``-suffixed validator keys, which duplicate the plain ones.

    The schema documents the two forms as equivalent, and the ``<>`` produces an
    anchor that doesn't round-trip (HTML-escaped in the id but not the href).
    """
    if isinstance(node, dict):
        properties = node.get('properties')
        if isinstance(properties, dict):
            for key in [k for k in properties if k.endswith('<>')]:
                del properties[key]
        for value in node.values():
            _drop_redundant_keys(value)
    elif isinstance(node, list):
        for item in node:
            _drop_redundant_keys(item)


def mirror_schemas_for_docs() -> None:
    """Copy the canonical schemas into ``_generated/``, rewritten for presentation.

    The domain only discovers files under the docs source dir, and the canonical
    schemas identify and reference one another with raw.githubusercontent URLs
    pinned to ``main`` -- noisy when rendered ("array of https://.../nodl...") and
    pointing at the wrong ref on PR/branch builds. Swapping every ``$id``/``$ref``
    for a short name makes the reference read "array of TopicEndpoint" with links
    resolving on-page. We also emit one ``.. json:schema::`` directive per
    definition so schema.md can ``.. include::`` it rather than list every type.
    The canonical schemas are untouched; only these copies change.
    """
    SCHEMA_DST.mkdir(parents=True, exist_ok=True)
    schemas = {p.name: yaml.safe_load(p.read_text()) for p in SCHEMA_SRC.glob('*.schema.yaml')}
    # Definition names are unique across files, so one map also covers the
    # cross-file ref (nodl's parameters -> parameter.schema.yaml).
    ref_map = {name: _short_id(name) for doc in schemas.values() for name in doc.get('definitions', {})}

    for filename, doc in schemas.items():
        stem = filename.split('.')[0]  # nodl.schema.yaml -> nodl
        doc['$id'] = _short_id(stem)
        for name, definition in doc.get('definitions', {}).items():
            definition['$id'] = ref_map[name]
        _rewrite_refs(doc, ref_map)
        _drop_redundant_keys(doc)
        (SCHEMA_DST / filename).write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))

        # .txt, not .rst, so Sphinx doesn't read the snippet as its own document.
        directives = '\n'.join(f'.. json:schema:: {ref_map[name]}' for name in doc.get('definitions', {}))
        (SCHEMA_DST / f'{stem}_definitions.txt').write_text(directives + '\n')


def patch_object_value_type() -> None:
    """Render a map's value type, e.g. "object of ParameterDefinition".

    The JSON domain renders every object as a bare "object" and ignores
    ``additionalProperties``, dropping the value type of string->schema maps like
    NoDL's ``parameters``. Append " of <value type>" (a link when the value is a
    ``$ref``), wrapping the original so an upstream change falls back to "object".
    """
    import docutils.nodes
    from sphinx_immaterial.apidoc.json import domain

    directive = domain.JsonSchemaDirective
    original = directive._get_type_description_line_object

    def with_value_type(self, schema_node):
        line = original(self, schema_node)
        value_schema = schema_node.get('additionalProperties')
        if isinstance(value_schema, dict):
            value_line = self._get_type_description_line(value_schema)
            if value_line:
                return (line or []) + [docutils.nodes.emphasis('', ' of ')] + value_line
        return line

    directive._get_type_description_line_object = with_value_type
