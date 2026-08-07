from typing import IO, Union
from nodl_schema.models import NodlDocument
import json
import yaml
from nodl_schema.validator import validate

def load_nodl(source: Union[str, bytes, IO], *, resolve: bool = True) -> NodlDocument:
    """Load and validate a NoDL document from a string, bytes, or file-like object.

    JSON is a subset of YAML, so both are accepted through yaml.safe_load.

    When ``resolve`` is true (the default) and the document has an ``include``
    list, each reference is resolved and its entities are merged in (see
    nodl_schema.composition); the returned document carries the merged
    interface and no ``include`` key. Pass ``resolve=False`` to parse the
    document as authored, leaving ``include`` intact and following nothing.

    Which references can be resolved depends on what is registered with
    nodl_schema.composition.register_resolver; there is no resolver argument
    here, so a form is made available by registering it rather than by every
    caller passing one down.

    Raises jsonschema.ValidationError on schema error, pydantic.ValidationError
    on type error, or composition.CompositionError on an unresolvable or
    conflicting include.
    """
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)

    if resolve and data.get('include'):
        # Imported lazily to avoid a circular import (composition validates included docs via this module).
        from nodl_schema.composition import resolve_document

        data = resolve_document(data)
        validate(data)

    # parse_obj is pydantic v1 API, retained as a deprecated alias in v2.
    # Used so this module works against both rosdep-shipped pydantic v1
    # (humble/jazzy/kilted) and v2 (lyrical+).
    return NodlDocument.parse_obj(data)

def _to_plain_dict(doc: NodlDocument) -> dict:
    """Serialize a model to a JSON-compatible dict that drops Nones and unwraps enums.

    Goes via .json() so the result is a plain dict on both pydantic v1 and v2;
    v2's mode='json' equivalent is not available in v1.
    """
    return json.loads(doc.json(exclude_none=True))

def dump_nodl(doc: Union[NodlDocument, dict], *, format: str = 'yaml') -> str:
    """Serialize a NodlDocument (or plain dict) to YAML or JSON string."""
    data = _to_plain_dict(doc) if isinstance(doc, NodlDocument) else doc
    if format == 'json':
        return json.dumps(data, indent=2)
    elif format == 'yaml':
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        raise ValueError(f'Unsupported format "{format}" for nodl serialization')
