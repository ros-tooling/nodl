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
``install_data`` installs the documents, registered with the ament index as ``ament_nodl_register()`` registers them in CMake.
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
    resource_name: str | None = None
    no_index: bool = False

    def __post_init__(self) -> None:
        if not self.target.isidentifier() or keyword.iskeyword(self.target):
            raise _setup_error(f"target '{self.target}' is not a valid Python identifier")
        if self.resource_name is None:
            return
        if self.no_index:
            raise _setup_error(
                f"target '{self.target}' is not registered with the ament index because of no_index, "
                f"so resource_name '{self.resource_name}' has no effect. Remove one of them."
            )
        if not self.resource_name:
            raise _setup_error(f"target '{self.target}' has a resource_name with no value")
        if '/' in self.resource_name:
            raise _setup_error(f"target '{self.target}' has a resource_name '{self.resource_name}' with a '/'")

    @property
    def resource(self) -> str:
        """The name the document is registered under."""
        return self.target if self.resource_name is None else self.resource_name


def nodl_generate_py(
    target: str, nodl_file: str, *, resource_name: str | None = None, no_index: bool = False
) -> Document:
    """Declare a node module to generate, with the arguments of the CMake function ``nodl_generate_py()``.

    The document is also registered with the ament index, as ``nodl://<package>/<resource_name>``.

    :param target: Name of the generated module, which must be a valid Python identifier.
        It is PascalCased for the class name, and a trailing ``_base`` is removed for the node name.
    :param nodl_file: Path to the NoDL document, relative to the directory the build runs in, which is the package directory.
    :param resource_name: Name to register the document under.
        The default is ``target``.
    :param no_index: Do not register the document with the ament index.
    :raises SetupError: When ``target`` is not a valid Python identifier,
        or ``resource_name`` is empty, contains a ``/`` or is given with ``no_index``.
    """
    return Document(target, nodl_file, resource_name, no_index)


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


def _register_documents(
    documents: tuple[Document, ...], package: str, staging_dir: Path
) -> list[tuple[str, list[str]]]:
    """Stage the documents as ``ament_nodl_register()`` installs them, and return them as ``data_files``.

    Each registered document is installed as ``nodl://<package>/<resource>``, and every ``local://`` include of another registered document is rewritten to that form.

    :raises SetupError: When a document cannot be rewritten, for example because it includes a file that is not registered.
    """
    from nodl_schema.rewrite import UnrewrittenReferenceError, rewrite_references

    registered = [document for document in documents if not document.no_index]
    if not registered:
        return []
    paths = {document.target: Path(document.nodl_file).resolve() for document in registered}
    rewrites = {f'local://{paths[document.target]}': f'nodl://{package}/{document.resource}' for document in registered}

    shutil.rmtree(staging_dir, ignore_errors=True)
    index_dir = staging_dir / 'index'
    share_dir = staging_dir / 'share'
    index_dir.mkdir(parents=True)
    share_dir.mkdir()
    for document in registered:
        try:
            text = rewrite_references(paths[document.target], rewrites)
        except UnrewrittenReferenceError as exc:
            raise _setup_error(
                f'{package}__{document.resource} includes a local:// reference that is not registered.\n{exc}\n'
                'Register the included file with nodl_generate_py() in the same package, '
                'so the reference can be rewritten to a nodl:// reference.'
            ) from exc
        except OSError as exc:
            raise _setup_error(f'{document.nodl_file}: {exc}') from exc
        (index_dir / f'{package}__{document.resource}').write_text(text)
        (share_dir / f'{document.resource}.nodl.yaml').write_text(text)
    return [
        ('share/ament_index/resource_index/nodl', [str(path) for path in sorted(index_dir.iterdir())]),
        (f'share/{package}/nodl', [str(path) for path in sorted(share_dir.iterdir())]),
    ]


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
        if any(not document.no_index for document in self._nodl_documents) and not self.distribution.has_data_files():
            raise _setup_error(
                'registering documents needs setup() to list data_files, such as the package resource marker, '
                'because without data_files setuptools does not run install_data and the documents would not install'
            )
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


class _RegisterInstallData:
    """Mixin for ``install_data`` that installs the registered documents next to the package's own data files."""

    _nodl_documents: tuple[Document, ...]

    def run(self):
        package = _read_package_name(Path('package.xml'))
        staging_dir = Path(self.get_finalized_command('build').build_base) / 'nodl_generated' / package / 'nodl'
        registered = _register_documents(self._nodl_documents, package, staging_dir)
        self.data_files = [*(self.data_files or []), *registered]
        super().run()


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


def _check_registrations(registered: list[Document]) -> None:
    """Check that no two documents register the same resource name or the same file."""
    names: dict[str, Document] = {}
    files: dict[Path, Document] = {}
    for document in registered:
        if document.resource in names:
            raise _setup_error(
                f"targets '{names[document.resource].target}' and '{document.target}' "
                f"both register the resource name '{document.resource}', "
                'resource names must be unique within a package. Set resource_name on one of them.'
            )
        path = Path(document.nodl_file).resolve()
        if path in files:
            raise _setup_error(
                f"targets '{files[path].target}' and '{document.target}' both register {document.nodl_file}, "
                'a file can be registered under only one name so local:// references to it rewrite unambiguously. '
                'Set no_index on one of them.'
            )
        names[document.resource] = files[path] = document


def nodl_cmdclass(*documents: Document, cmdclass: Mapping[str, type] | None = None) -> dict[str, type]:
    """Return the ``cmdclass`` for ``setup()`` that generates ``documents`` when the package is built.

    :param documents: Declarations made with :func:`nodl_generate_py`.
    :param cmdclass: The package's own command classes by command name, to wrap in place of setuptools' defaults.
        Commands that are not wrapped stay in the result as given.
    :raises SetupError: When there are no documents, two have the same target,
        two register the same resource name, or two register the same file.
    """
    # setuptools is imported at the top of this module, so distutils is the copy that setuptools uses.
    from distutils.command.install_data import install_data

    import setuptools.command.build_py
    import setuptools.command.develop

    if not documents:
        raise _setup_error('nodl_cmdclass() needs at least one document, made with nodl_generate_py()')
    targets = [document.target for document in documents]
    duplicate = next((target for target in targets if targets.count(target) > 1), None)
    if duplicate is not None:
        raise _setup_error(f"target '{duplicate}' is declared more than once, targets must be unique")
    _check_registrations([document for document in documents if not document.no_index])

    commands = dict(cmdclass or {})
    wrapped = {
        'build_py': (setuptools.command.build_py.build_py, _GenerateBuildPy, {'_nodl_documents': documents}),
        'install_data': (install_data, _RegisterInstallData, {'_nodl_documents': documents}),
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
