# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Generate NoDL node modules in an ``ament_python`` package, as ``nodl_generate_py()`` does in CMake.

A package opts in from its ``setup.py``:

.. code-block:: python

    from nodl_generator_py.ament_python import nodl_cmdclass, nodl_generate_py

    setup(
        ...,
        cmdclass=nodl_cmdclass(nodl_generate_py('echo_node_base', 'nodl/echo_node.nodl.yaml')),
    )

``build_py`` generates the modules into the build base, never into the source tree, and builds them as the package's ``generated`` subpackage.
Every command that builds or installs a package runs ``build_py``, so those commands need no wrapper.
``develop`` and ``editable_wheel`` fail with an error, because they cannot import modules that are not in the source tree.
"""

from __future__ import annotations

import keyword
import os
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from setuptools.errors import SetupError

if TYPE_CHECKING:
    from catkin_pkg.package import Package

RUNTIME_PACKAGE = 'nodl_runtime_py'


def _setup_error(message: str) -> SetupError:
    """Return an error that setuptools reports as ``error: <message>`` without a traceback."""
    return SetupError(f'nodl_generator_py: {message}')


@dataclass(frozen=True)
class Document:
    """A NoDL document to generate a node module from, as declared by :func:`nodl_generate_py`."""

    target: str
    nodl_file: str

    def __post_init__(self) -> None:
        if not self.target.isidentifier() or keyword.iskeyword(self.target):
            raise _setup_error(f"target '{self.target}' is not a valid Python identifier")


def nodl_generate_py(target: str, nodl_file: str) -> Document:
    """Declare a node module to generate, with the arguments of the CMake function ``nodl_generate_py()``.

    :param target: Name of the generated module, which must be a valid Python identifier.
        It is PascalCased for the class name, and a trailing ``_base`` is removed for the node name.
    :param nodl_file: Path to the NoDL document, relative to the directory the build runs in, which is the package directory.
    :raises SetupError: When ``target`` is not a valid Python identifier.
    """
    return Document(target, nodl_file)


def _read_package(package_xml: Path) -> Package:
    from catkin_pkg.package import InvalidPackage, parse_package

    try:
        package = parse_package(str(package_xml))
    except (InvalidPackage, OSError) as exc:
        raise _setup_error(f'cannot read {package_xml}: {exc}') from exc
    package.evaluate_conditions(os.environ)
    return package


def _read_package_name(package_xml: Path) -> str:
    """Return the package name from ``package_xml``."""
    return _read_package(package_xml).name


def _check_runtime_dependency(package_xml: Path) -> None:
    """Check that ``package_xml`` declares a runtime dependency on nodl_runtime_py.

    Generated code imports what ``nodl_runtime_py`` provides, so a package without the dependency fails when it runs.

    :raises SetupError: When ``package_xml`` cannot be read, or does not declare the dependency.
    """
    package = _read_package(package_xml)
    exec_depends = [depend.name for depend in package.exec_depends if depend.evaluated_condition is not False]
    if RUNTIME_PACKAGE not in exec_depends:
        raise _setup_error(
            f"package '{package.name}' must declare a runtime dependency on {RUNTIME_PACKAGE}, "
            'which generated code needs when it runs. '
            f'Add <exec_depend>{RUNTIME_PACKAGE}</exec_depend> to its package.xml.'
        )


def _check_package(package: str, packages: Iterable[str], package_dir: Mapping[str, str]) -> None:
    """Check that ``package`` can get a ``generated`` subpackage.

    :param packages: The packages that ``setup()`` lists.
    :param package_dir: The ``package_dir`` of ``setup()``, mapping a package to its directory.
    :raises SetupError: When ``package`` is not listed, or already has a ``generated`` subpackage.
    """
    packages = list(packages)
    if package not in packages:
        raise _setup_error(
            f"generated modules install as '{package}.generated', but setup() does not list the package '{package}'"
        )
    source = Path(package_dir.get(package, os.path.join(package_dir.get('', ''), package)))
    if f'{package}.generated' in packages or (source / 'generated').exists():
        raise _setup_error(
            f"the package '{package}' already has a 'generated' subpackage, "
            'but nodl_generator_py installs generated code as that subpackage. Rename it.'
        )


def _generate_modules(documents: tuple[Document, ...], generated_dir: Path) -> None:
    import yaml
    from jsonschema import ValidationError

    from nodl_generator_common.plan import CodegenError
    from nodl_generator_py.generator import generate_python, write_generation
    from nodl_schema.composition import MergeError, ResolutionError

    shutil.rmtree(generated_dir, ignore_errors=True)
    generated_dir.mkdir(parents=True)
    (generated_dir / '__init__.py').touch()
    for document in documents:
        source = Path(document.nodl_file)
        try:
            # The resolver of local:// includes needs an absolute path.
            write_generation(generate_python(source.resolve(), document.target), generated_dir, document.target)
        except (CodegenError, MergeError, ResolutionError, ValidationError, ValueError, yaml.YAMLError, OSError) as exc:
            raise _setup_error(f'{source}: {exc}') from exc


class _GenerateBuildPy:
    """Mixin for ``build_py`` that builds the documents as the ``generated`` subpackage of the package in ``package.xml``."""

    _nodl_documents: tuple[Document, ...]
    _nodl_declared = False

    def _generated_dir(self, package: str) -> Path:
        return Path(self.get_finalized_command('build').build_base) / 'nodl_generated' / package / 'generated'

    def _relative_generated_dir(self, package: str) -> str:
        # setuptools rejects an absolute package directory.
        return os.path.relpath(self._generated_dir(package))

    def _declare_generated(self, package: str) -> None:
        if self._nodl_declared:
            return
        self.packages = [*(self.packages or []), f'{package}.generated']
        self.package_dir = {**self.package_dir, f'{package}.generated': self._relative_generated_dir(package)}
        self._nodl_declared = True

    def run(self):
        _check_runtime_dependency(Path('package.xml'))
        package = _read_package_name(Path('package.xml'))
        # get_outputs may have declared the generated package already, which is not one of the package's own.
        own = [name for name in self.packages or [] if not (self._nodl_declared and name == f'{package}.generated')]
        _check_package(package, own, self.package_dir)
        _generate_modules(self._nodl_documents, self._generated_dir(package))
        # An earlier build leaves the modules of documents that are no longer declared, which an install would copy.
        shutil.rmtree(Path(self.build_lib) / package / 'generated', ignore_errors=True)
        self._declare_generated(package)
        super().run()

    def get_outputs(self, include_bytecode=1):
        # `install --skip-build` does not run build_py, but records what an earlier build left in the build space.
        if not self._nodl_declared:
            package = _read_package_name(Path('package.xml'))
            if self._generated_dir(package).is_dir():
                self._declare_generated(package)
        return super().get_outputs(include_bytecode)


class _RefuseSymlinkInstall:
    """Mixin for ``develop`` and ``editable_wheel``, which cannot import the generated modules yet.

    ``develop --uninstall`` still runs, so an earlier develop install can be removed.
    """

    def run(self):
        if getattr(self, 'uninstall', False):
            # Removing an earlier develop install generates nothing.
            return super().run()
        raise _setup_error(
            'editable installs, including colcon build --symlink-install, are not supported yet. '
            'Build without --symlink-install.'
        )


def _wrap(base: type, mixin: type, **attributes) -> type:
    return type(base.__name__, (mixin, base), attributes)


def nodl_cmdclass(*documents: Document, cmdclass: Mapping[str, type] | None = None) -> dict[str, type]:
    """Return the ``cmdclass`` for ``setup()`` that generates ``documents`` when the package is built.

    :param documents: Declarations made with :func:`nodl_generate_py`.
    :param cmdclass: The package's own command classes by command name, to wrap in place of setuptools' defaults.
        Commands that are not wrapped stay in the result as given.
    :raises SetupError: When there are no documents, or two have the same target.
    """
    import setuptools.command.build_py
    import setuptools.command.develop

    if not documents:
        raise _setup_error('nodl_cmdclass() needs at least one document, made with nodl_generate_py()')
    targets = [document.target for document in documents]
    duplicate = next((target for target in targets if targets.count(target) > 1), None)
    if duplicate is not None:
        raise _setup_error(f"target '{duplicate}' is declared more than once, targets must be unique")

    commands = dict(cmdclass or {})
    wrapped = {
        'build_py': (setuptools.command.build_py.build_py, _GenerateBuildPy, {'_nodl_documents': documents}),
        'develop': (setuptools.command.develop.develop, _RefuseSymlinkInstall, {}),
    }
    try:
        from setuptools.command.editable_wheel import editable_wheel

        wrapped['editable_wheel'] = (editable_wheel, _RefuseSymlinkInstall, {})
    except ImportError:
        pass
    for name, (default, mixin, attributes) in wrapped.items():
        commands[name] = _wrap(commands.get(name, default), mixin, **attributes)
    return commands
