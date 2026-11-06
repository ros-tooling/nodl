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

``build_py`` generates the modules into the build base, never into the source tree, and builds them as the package ``nodl_generated.<package>``.
``nodl_generated`` is a namespace package, so nothing installs a ``nodl_generated/__init__.py`` and the modules of many packages merge.
Every command that builds or installs a package runs ``build_py``, so those commands need no wrapper.
``install_data`` installs the documents, registered with the ament index as ``ament_nodl_register()`` registers them in CMake.
``develop`` is what ``colcon build --symlink-install`` runs in the build space.
It generates the modules into ``nodl_generated/<package>`` in the install directory of the ``develop``, where colcon puts the install space on ``PYTHONPATH``.
Outside colcon, ``setup.py develop`` installs them into its install directory in the same way, and ``develop --uninstall`` removes them.
colcon installs the documents with its ``symlink_data`` command, which is wrapped as ``install_data`` is.
``editable_wheel`` fails with an error, because it cannot import modules that are not in the source tree.
``build`` fails when ``setup()`` lists no package or module, because the generated modules install with ``build_py``, which setuptools then does not run.
"""

from __future__ import annotations

import keyword
import os
import shutil
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from importlib.metadata import entry_points
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


def _generated_dir(build_base: str | Path, package: str) -> Path:
    return Path(build_base) / 'nodl_staging' / package / 'py'


def _generate_modules(documents: tuple[Document, ...], generated_dir: Path, project: Path = Path()) -> None:
    import yaml
    from jsonschema import ValidationError

    from nodl_generator_common.plan import CodegenError
    from nodl_generator_py.generator import generate_python, write_generation
    from nodl_schema.composition import MergeError, ResolutionError

    shutil.rmtree(generated_dir, ignore_errors=True)
    generated_dir.mkdir(parents=True)
    (generated_dir / '__init__.py').touch()
    for document in documents:
        source = project / document.nodl_file
        try:
            # The resolver of local:// includes needs an absolute path.
            write_generation(generate_python(source.resolve(), document.target), generated_dir, document.target)
        except (CodegenError, MergeError, ResolutionError, ValidationError, ValueError, yaml.YAMLError, OSError) as exc:
            raise _setup_error(f'{source}: {exc}') from exc


def _register_documents(
    documents: tuple[Document, ...], package: str, staging_dir: Path, project: Path = Path()
) -> list[tuple[str, list[str]]]:
    """Stage the documents as ``ament_nodl_register()`` installs them, and return them as ``data_files``.

    Each registered document is installed as ``nodl://<package>/<resource>``, and every ``local://`` include of another registered document is rewritten to that form.

    :raises SetupError: When a document cannot be rewritten, for example because it includes a file that is not registered.
    """
    from nodl_schema.rewrite import UnrewrittenReferenceError, rewrite_references

    registered = [document for document in documents if not document.no_index]
    if not registered:
        return []
    paths = {document.target: (project / document.nodl_file).resolve() for document in registered}
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


def _generate_package(documents: tuple[Document, ...], project: Path, generated_dir: Path) -> None:
    """Check that the package in ``project`` can run generated modules, and generate them into ``generated_dir``."""
    _check_runtime_dependency(project / 'package.xml')
    _generate_modules(documents, generated_dir, project)


def _check_data_files(documents: tuple[Document, ...], distribution) -> None:
    if any(not document.no_index for document in documents) and not distribution.has_data_files():
        raise _setup_error(
            'registering documents needs setup() to list data_files, such as the package resource marker, '
            'because without data_files setuptools does not run install_data and the documents would not install'
        )


class _GenerateBuildPy:
    """Mixin for ``build_py`` that builds the documents as the package ``nodl_generated.<package>``, for the package in ``package.xml``."""

    _nodl_documents: tuple[Document, ...]
    _nodl_declared = False

    def _declare_generated(self, package: str) -> None:
        if self._nodl_declared:
            return
        name = f'nodl_generated.{package}'
        # setuptools rejects an absolute package directory.
        generated_dir = os.path.relpath(_generated_dir(self.get_finalized_command('build').build_base, package))
        self.packages = [*(self.packages or []), name]
        self.package_dir = {**self.package_dir, name: generated_dir}
        self._nodl_declared = True

    def run(self):
        package = _read_package_name(Path('package.xml'))
        _check_data_files(self._nodl_documents, self.distribution)
        _generate_package(
            self._nodl_documents, Path(), _generated_dir(self.get_finalized_command('build').build_base, package)
        )
        # An earlier build leaves the modules of documents that are no longer declared, which an install would copy.
        shutil.rmtree(Path(self.build_lib) / 'nodl_generated' / package, ignore_errors=True)
        self._declare_generated(package)
        super().run()

    def get_outputs(self, include_bytecode=1):
        # `install --skip-build` does not run build_py, but records what an earlier build left in the build space.
        if not self._nodl_declared:
            package = _read_package_name(Path('package.xml'))
            if _generated_dir(self.get_finalized_command('build').build_base, package).is_dir():
                self._declare_generated(package)
        return super().get_outputs(include_bytecode)


def _project_dir(distribution) -> Path:
    """Return the directory of ``setup.py``, where ``package.xml`` and the documents are.

    In the build space of a symlink install, ``setup.py`` is a symlink to the source tree, and the documents are only there.
    """
    return Path(distribution.script_name).resolve().parent


class _RegisterInstallData:
    """Mixin for ``install_data`` and colcon's ``symlink_data`` that installs the registered documents next to the package's own data files."""

    _nodl_documents: tuple[Document, ...]

    def run(self):
        project = _project_dir(self.distribution)
        package = _read_package_name(project / 'package.xml')
        staging_dir = Path(self.get_finalized_command('build').build_base) / 'nodl_staging' / package / 'nodl'
        registered = _register_documents(self._nodl_documents, package, staging_dir, project)
        self.data_files = [*(self.data_files or []), *registered]
        super().run()


class _GenerateDevelop:
    """Mixin for ``develop`` that installs the generated modules, as ``nodl_generated/<package>``, in the install directory.

    The install directory is where ``develop`` writes its ``.egg-link``, so it is never the source tree.
    Only the ``.py`` files are installed, as a plain install does.
    ``develop --uninstall``, which colcon runs to undo a symlink install, removes them.
    """

    _nodl_documents: tuple[Document, ...]

    def run(self):
        project = _project_dir(self.distribution)
        package = _read_package_name(project / 'package.xml')
        generated_dir = Path(self.install_dir) / 'nodl_generated' / package
        shutil.rmtree(generated_dir, ignore_errors=True)
        if not self.uninstall:
            _check_data_files(self._nodl_documents, self.distribution)
            with tempfile.TemporaryDirectory() as staging_dir:
                _generate_package(self._nodl_documents, project, Path(staging_dir) / 'py')
                shutil.copytree(Path(staging_dir) / 'py', generated_dir, ignore=shutil.ignore_patterns('*.yaml'))
        super().run()


class _RequireModules:
    """Mixin for ``build`` that fails when ``setup()`` lists no package or module."""

    def run(self):
        if not self.distribution.has_pure_modules():
            raise _setup_error(
                'setup() must list a package or module, because the generated modules install with build_py, '
                'which setuptools does not run without one'
            )
        super().run()


class _RefuseEditableWheel:
    """Mixin for ``editable_wheel``, which cannot import the generated modules."""

    def run(self):
        raise _setup_error(
            'editable installs with pip are not supported. '
            'Install the package, or build with colcon build --symlink-install, which needs setuptools older than 80.'
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

    try:
        from setuptools.command.build import build
    except ImportError:
        from distutils.command.build import build

    if not documents:
        raise _setup_error('nodl_cmdclass() needs at least one document, made with nodl_generate_py()')
    targets = [document.target for document in documents]
    duplicate = next((target for target in targets if targets.count(target) > 1), None)
    if duplicate is not None:
        raise _setup_error(f"target '{duplicate}' is declared more than once, targets must be unique")
    _check_registrations([document for document in documents if not document.no_index])

    commands = dict(cmdclass or {})
    wrapped = {
        'build': (build, _RequireModules, {}),
        'build_py': (setuptools.command.build_py.build_py, _GenerateBuildPy, {'_nodl_documents': documents}),
        'install_data': (install_data, _RegisterInstallData, {'_nodl_documents': documents}),
    }
    # From setuptools 80, develop only runs pip install -e, which fails through editable_wheel.
    if any(option[0].rstrip('=') == 'uninstall' for option in setuptools.command.develop.develop.user_options):
        wrapped['develop'] = (setuptools.command.develop.develop, _GenerateDevelop, {'_nodl_documents': documents})
    try:
        from setuptools.command.editable_wheel import editable_wheel

        wrapped['editable_wheel'] = (editable_wheel, _RefuseEditableWheel, {})
    except ImportError:
        pass
    # colcon's data command for a symlink install is not one of the setuptools commands, it is found by its entry point.
    for entry in entry_points(group='distutils.commands', name='symlink_data'):
        with suppress(ImportError):
            wrapped['symlink_data'] = (entry.load(), _RegisterInstallData, {'_nodl_documents': documents})
    for name, (default, mixin, attributes) in wrapped.items():
        commands[name] = _wrap(commands.get(name, default), mixin, **attributes)
    return commands
