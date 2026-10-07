# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Convert NoDL parameters to generate_parameter_library format."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from generate_parameter_library_py.parse_yaml import GenerateCode

from nodl_generator_common.generated_file import GeneratedFile
from nodl_generator_common.parameters import nest_dotted_parameters
from nodl_generator_cpp.include_prefix import prefixed
from nodl_schema.models import ParameterDefinition


def _param_to_dict(param: ParameterDefinition) -> dict:
    """Convert a ParameterDefinition to a genparamlib-compatible dict.

    Uses ``.json()`` + ``json.loads()`` rather than ``.dict()`` because
    pydantic v1's ``.dict()`` keeps enum objects (e.g. ``ScalarType.double``
    instead of ``"double"``) and doesn't apply ``by_alias`` to nested
    models like ``Validation`` (whose fields use ``<>`` aliases such as
    ``bounds<>``).
    """
    return json.loads(param.json(by_alias=True, exclude_none=True))


def generate_genparamlib_yaml(
    target_name: str,
    parameters: dict[str, ParameterDefinition],
    *,
    namespace: str | None = None,
) -> GeneratedFile:
    """Convert NoDL parameters to a generate_parameter_library YAML file.

    The top-level key becomes the C++ namespace of the generated structs,
    so a *namespace* yields ``<namespace>::<target_name>``.
    It does not affect ROS parameter names.

    Returns a :class:`GeneratedFile` containing the YAML content, ready
    to be written to disk and then passed to
    :func:`generate_parameter_header`.
    """
    params_dict = nest_dotted_parameters({name: _param_to_dict(param) for name, param in parameters.items()})
    content = yaml.dump(
        {f'{namespace}::{target_name}' if namespace else target_name: params_dict},
        default_flow_style=False,
        sort_keys=False,
        explicit_start=True,
    )
    return GeneratedFile(
        filename=f'{target_name}_parameters.yaml',
        content=content,
    )


def generate_parameter_header(yaml_path: Path, *, include_prefix: str | None = None) -> GeneratedFile:
    """Generate a C++ parameter header from a genparamlib YAML file on disk.

    Delegates to :class:`generate_parameter_library_py.parse_yaml.GenerateCode`
    to produce the header content.

    Returns a :class:`GeneratedFile` with the header content.
    Its ``filename`` is placed under *include_prefix* when it is given.
    """
    gen = GenerateCode('cpp')
    gen.parse(str(yaml_path), '')
    return GeneratedFile(
        filename=prefixed(include_prefix, yaml_path.stem + '.hpp'),
        content=str(gen),
    )
