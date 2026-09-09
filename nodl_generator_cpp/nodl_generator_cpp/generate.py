# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import re
from dataclasses import dataclass
from pathlib import Path

from nodl_generator_common.generated_file import GeneratedFile
from nodl_generator_common.provenance import resolve_provenance
from nodl_generator_cpp.cmake_deps import (
    format_cmake_deps,
    generated_filenames,
    ros_deps,
)
from nodl_generator_cpp.models import CodegenCpp, Role
from nodl_generator_cpp.params import generate_genparamlib_yaml
from nodl_generator_cpp.provenance import codegen_cpp
from nodl_generator_cpp.template import render_templates

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class CodegenError(Exception):
    """Raised when codegen-specific validation fails.

    Covers provenance errors such as conflicting base classes,
    missing codegen metadata, and unsupported codegen roles.
    """


def _validate_target_name(target_name: str) -> None:
    """Validate that *target_name* is a valid C++ identifier.

    Raises :class:`ValueError` if the name is empty or not a valid
    C++ identifier (letter or underscore followed by alphanumerics/underscores).
    """
    if not target_name or not _IDENTIFIER_RE.match(target_name):
        raise ValueError(f'target_name must be a valid C++ identifier, got {target_name!r}')


def _find_base_class_config(barriers: list[CodegenCpp]) -> tuple[str, str]:
    """Find the single base-class config from the provenance barriers.

    Filters *barriers* to those with ``role == BASE_CLASS`` and ensures
    exactly one exists.

    Returns ``(class, header)`` — the C++ class name and its header.

    Raises :class:`CodegenError` if there is no base class or if
    multiple conflicting base classes are found.
    """
    base_classes = [b for b in barriers if b.role is Role.BASE_CLASS]
    if not base_classes:
        raise CodegenError(
            'No base class found. Include a base-class provider (e.g. nodl://rclcpp/node) in your NoDL document.'
        )
    if len(base_classes) > 1:
        classes = ', '.join(b.class_ for b in base_classes if b.class_ is not None)
        raise CodegenError(
            f'Multiple conflicting base class providers found: {classes}. '
            'A generated node can only inherit from one base class.'
        )
    assert base_classes[0].class_ is not None
    assert base_classes[0].header is not None
    return base_classes[0].class_, base_classes[0].header


@dataclass
class CmakeDepsResult:
    """Data needed to write a ``<target>_deps.cmake`` file."""

    sources: list[Path]
    ros_deps: list[str]
    generated_filenames: list[str]

    def format(self, target: str) -> str:
        """Render the CMake deps file content."""
        return format_cmake_deps(target, self.sources, self.ros_deps, self.generated_filenames)


def cmake_deps(source: Path, target_name: str) -> CmakeDepsResult:
    """Compute CMake dependency information from a NoDL document.

    Runs the same load → provenance → filter pipeline as :func:`generate_cpp` but stops before template rendering.

    Returns a :class:`CmakeDepsResult` containing the NoDL source paths, ROS package dependencies,
    and the list of files the generator will produce.
    """
    _validate_target_name(target_name)

    resolved = resolve_provenance(source, codegen_cpp)

    _find_base_class_config(resolved.barriers)  # validates single base class

    has_parameters = len(resolved.entities.parameters) > 0

    return CmakeDepsResult(
        sources=resolved.sources,
        ros_deps=ros_deps(
            resolved.barriers,
            resolved.entities.publishers,
            resolved.entities.subscriptions,
            resolved.entities.service_servers,
            resolved.entities.service_clients,
            resolved.entities.action_servers,
            resolved.entities.action_clients,
        ),
        generated_filenames=generated_filenames(target_name, has_parameters),
    )


def generate_cpp(source: Path, target_name: str) -> list[GeneratedFile]:
    """Generate C++ base-node class files from a NoDL document.

    Loads and resolves the NoDL document at *source* (a filesystem path),
    walks the include tree for provenance, and renders the C++ header
    and source files.

    Returns a list of :class:`GeneratedFile` objects ready to be written
    to disk by the caller.
    """
    _validate_target_name(target_name)

    resolved = resolve_provenance(source, codegen_cpp)

    base_class, base_header = _find_base_class_config(resolved.barriers)

    has_parameters = len(resolved.entities.parameters) > 0

    generated_files = []
    generated_files += render_templates(
        target_name,
        base_class,
        base_header,
        resolved.entities.publishers,
        resolved.entities.subscriptions,
        resolved.entities.service_servers,
        resolved.entities.service_clients,
        resolved.entities.action_servers,
        resolved.entities.action_clients,
        has_parameters,
    )
    if has_parameters:
        generated_files += [generate_genparamlib_yaml(target_name, resolved.entities.parameters)]

    return generated_files
