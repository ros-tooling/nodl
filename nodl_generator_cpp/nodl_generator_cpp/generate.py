# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from nodl_generator_common.generated_file import GeneratedFile
from nodl_generator_common.plan import CodegenError, CodegenPlanner, CodegenSchema, Walk, plan
from nodl_generator_cpp.cmake_deps import (
    format_cmake_deps,
    generated_filenames,
    ros_deps,
)
from nodl_generator_cpp.include_prefix import validate_include_prefix
from nodl_generator_cpp.models import CodegenBaseClass, CodegenNode, CodegenNoGenerate
from nodl_generator_cpp.params import generate_genparamlib_yaml
from nodl_generator_cpp.template import render_templates
from nodl_schema.loader import IncludedDocument

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# The parsed ``codegen.cpp`` metadata, one model per ``role``.
CodegenCpp = Union[CodegenBaseClass, CodegenNoGenerate, CodegenNode]
_ROLE_MODELS: dict[str, type[CodegenCpp]] = {
    'BASE_CLASS': CodegenBaseClass,
    'NO_GENERATE': CodegenNoGenerate,
    'NODE': CodegenNode,
}

CODEGEN_CPP_SCHEMA = CodegenSchema(
    key='cpp',
    schema=Path(__file__).parent / 'schemas' / 'codegen_cpp.schema.yaml',
    parse=lambda config: _ROLE_MODELS[config['role']].parse_obj(config),
    tag='role',
)


class CppPlanner(CodegenPlanner[CodegenCpp]):
    """Find the base class and namespace, and generate every included document without ``codegen.cpp``.

    The root may have role ``NODE``, whose ``namespace`` sets :attr:`namespace`.
    The walk stops at an included document with ``codegen.cpp``, since it already has an implementation.
    ``BASE_CLASS`` contributes its class, and ``NO_GENERATE`` contributes nothing.
    :meth:`finalize` sets :attr:`base_class` to the single base class.
    """

    def __init__(self) -> None:
        self.base_classes: list[CodegenBaseClass] = []
        self.namespace: Optional[str] = None
        self._errors: list[str] = []
        self._base_class: Optional[CodegenBaseClass] = None

    @property
    def base_class(self) -> CodegenBaseClass:
        """The single base class.

        Raises :class:`RuntimeError` before :meth:`finalize` sets it.
        """
        if self._base_class is None:
            raise RuntimeError('base_class is not set until finalize() succeeds')
        return self._base_class

    def root(self, config: Optional[CodegenCpp]) -> None:
        if config is None:
            return
        if isinstance(config, CodegenNode):
            self.namespace = config.namespace
        else:
            self._errors.append(
                f'The root document has codegen.cpp role {config.role}, '
                'which describes included provider documents, not the generated root. '
                'Use role NODE or omit codegen.cpp on the root document.'
            )

    def visit(self, included: IncludedDocument, config: Optional[CodegenCpp]) -> Walk:
        if config is None:
            return Walk.CONTINUE
        if isinstance(config, CodegenBaseClass):
            self.base_classes.append(config)
        elif isinstance(config, CodegenNode):
            self._errors.append(
                'codegen.cpp role NODE is only valid on the root document being generated, '
                f'but {included.ref} ({included.path}) declares it.'
            )
        return Walk.STOP

    def finalize(self) -> None:
        """Set :attr:`base_class` to the single base class.

        Raises :class:`CodegenError` if a document has a role that is invalid where it is,
        if there is no base class, or if multiple conflicting base classes are found.
        """
        if self._errors:
            raise CodegenError('\n'.join(self._errors))
        if not self.base_classes:
            raise CodegenError(
                'No base class found. Include a base-class provider '
                '(e.g. nodl://nodl_common_interfaces/node) in your NoDL document.'
            )
        if len(self.base_classes) > 1:
            classes = ', '.join(b.class_ for b in self.base_classes)
            raise CodegenError(
                f'Multiple conflicting base class providers found: {classes}. '
                'A generated node can only inherit from one base class.'
            )
        self._base_class = self.base_classes[0]


def _validate_target_name(target_name: str) -> None:
    """Validate that *target_name* is a valid C++ identifier.

    Raises :class:`ValueError` if the name is empty or not a valid
    C++ identifier (letter or underscore followed by alphanumerics/underscores).
    """
    if not target_name or not _IDENTIFIER_RE.match(target_name):
        raise ValueError(f'target_name must be a valid C++ identifier, got {target_name!r}')


@dataclass
class CmakeDepsResult:
    """Data needed to write a ``<target>_deps.cmake`` file."""

    sources: list[Path]
    ros_deps: list[str]
    generated_filenames: list[str]

    def format(self, target: str) -> str:
        """Render the CMake deps file content."""
        return format_cmake_deps(target, self.sources, self.ros_deps, self.generated_filenames)


def cmake_deps(source: Path, target_name: str, *, include_prefix: str | None = None) -> CmakeDepsResult:
    """Compute CMake dependency information from a NoDL document.

    Plans generation the same way as :func:`generate_cpp` but stops before template rendering.

    Returns a :class:`CmakeDepsResult` containing the NoDL source paths, ROS package dependencies,
    and the list of files the generator will produce.
    The file paths are relative to the output directory and include *include_prefix* for headers.
    """
    _validate_target_name(target_name)
    validate_include_prefix(include_prefix)

    planner = CppPlanner()
    planned = plan(source, CODEGEN_CPP_SCHEMA, planner)
    doc = planned.doc

    has_parameters = bool(doc.parameters)

    return CmakeDepsResult(
        sources=planned.sources,
        ros_deps=ros_deps(
            planner.base_class.header,
            doc.publishers or [],
            doc.subscriptions or [],
            doc.service_servers or [],
            doc.service_clients or [],
            doc.action_servers or [],
            doc.action_clients or [],
        ),
        generated_filenames=generated_filenames(target_name, has_parameters, include_prefix=include_prefix),
    )


def generate_cpp(source: Path, target_name: str, *, include_prefix: str | None = None) -> list[GeneratedFile]:
    """Generate C++ base-node class files from a NoDL document.

    Loads and resolves the NoDL document at *source* (a filesystem path),
    walks the include tree for the documents it owns and its base class,
    and renders the C++ header and source files.

    When *include_prefix* is given, the header is placed under it and the source includes it from there.
    The ``filename`` of each returned file is relative to the output directory.

    Returns a list of :class:`GeneratedFile` objects ready to be written
    to disk by the caller.
    """
    _validate_target_name(target_name)
    validate_include_prefix(include_prefix)

    planner = CppPlanner()
    planned = plan(source, CODEGEN_CPP_SCHEMA, planner)
    doc = planned.doc
    base = planner.base_class

    has_parameters = bool(doc.parameters)

    generated_files = []
    generated_files += render_templates(
        target_name,
        base.class_,
        base.header,
        doc.publishers or [],
        doc.subscriptions or [],
        doc.service_servers or [],
        doc.service_clients or [],
        doc.action_servers or [],
        doc.action_clients or [],
        has_parameters,
        include_prefix=include_prefix,
        namespace=planner.namespace,
    )
    if has_parameters:
        generated_files += [generate_genparamlib_yaml(target_name, doc.parameters, namespace=planner.namespace)]

    return generated_files
