# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""setuptools extension that gives ``ament_python`` packages what ``nodl_generate_py`` gives ``ament_cmake`` packages.

``nodl_generator_py`` registers :func:`install_commands` as a ``setuptools.finalize_distribution_options`` hook.
That runs before ``setup.cfg`` is parsed, so the hook looks for the ``nodl_generate_py`` and ``nodl_add_py_executable`` sections in the configuration files itself.
It wraps nothing for a package without them, so such a package builds as it would without ``nodl_generator_py``.
For a package with them, the hook wraps the commands that build and install a package.
Each wrapped command reads the sections from ``setup.cfg`` when it runs.

* ``nodl_generate_py.<target>`` generates a NoDL document into the package's ``generated`` subpackage.
  It takes ``nodl_file``, ``resource_name`` and ``no_index``, like ``nodl_generate_py()`` in CMake.
* ``nodl_add_py_executable.<executable>`` installs a script that runs a node class with ``run_node``.
  It takes ``target`` and ``executor``.

Everything is generated into the ``nodl_generated`` directory of the build base, never into the source tree,
and added to the distribution's ``packages``, ``data_files`` and ``scripts`` before the commands that install them.
A develop install copies the scripts itself, because ``setup.py develop`` would wrap them in scripts that import ``pkg_resources``.
"""

from __future__ import annotations

import keyword
import os
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

GENERATE_SECTION = 'nodl_generate_py'
EXECUTABLE_SECTION = 'nodl_add_py_executable'
RUNTIME_PACKAGE = 'nodl_runtime_py'
DOCUMENT_OPTIONS = ('nodl_file', 'resource_name', 'no_index')
EXECUTABLE_OPTIONS = ('target', 'executor')

_TRUE = {'1', 'true', 'yes', 'on'}
_FALSE = {'0', 'false', 'no', 'off'}
_APPLIED = '_nodl_generator_py_applied'
_SECTION = re.compile(rf'^\[({GENERATE_SECTION}|{EXECUTABLE_SECTION})[.\]]', re.MULTILINE)


def _setup_error(message: str) -> Exception:
    """Return an error that setuptools reports as ``error: <message>`` without a traceback."""
    from distutils.errors import DistutilsSetupError

    return DistutilsSetupError(f'nodl_generator_py: {message}')


@dataclass(frozen=True)
class Document:
    """A ``nodl_generate_py.<target>`` section."""

    target: str
    nodl_file: str
    resource_name: str | None
    index: bool

    @property
    def resource(self) -> str:
        """The name the document is registered under."""
        return self.target if self.resource_name is None else self.resource_name


@dataclass(frozen=True)
class Executable:
    """A ``nodl_add_py_executable.<name>`` section."""

    name: str
    target: str
    executor: str | None


@dataclass(frozen=True)
class Config:
    """Everything ``setup.cfg`` asks nodl_generator_py to generate."""

    documents: tuple[Document, ...]
    executables: tuple[Executable, ...]


def _is_nodl_section(section: str) -> bool:
    return any(section == name or section.startswith(f'{name}.') for name in (GENERATE_SECTION, EXECUTABLE_SECTION))


def _sections(command_options: Mapping, kind: str) -> list[tuple[str, str, dict[str, str]]]:
    """Return ``(section, name, options)`` for each section named ``<kind>.<name>``, and reject one without a name."""
    sections = []
    for section, options in command_options.items():
        if section != kind and not section.startswith(f'{kind}.'):
            continue
        name = section[len(kind) + 1 :]
        if not name:
            raise _setup_error(f'[{section}] needs a name, as in [{kind}.<name>]')
        sections.append((section, name, {key: value for key, (_, value) in options.items()}))
    return sections


def _check_options(section: str, options: Mapping[str, str], valid: tuple[str, ...], required: str) -> None:
    unknown = [key for key in options if key not in valid]
    if unknown:
        raise _setup_error(f"[{section}] has unknown option '{unknown[0]}', expected one of: {', '.join(valid)}")
    if required not in options:
        raise _setup_error(f'[{section}] needs the option {required}')
    for key, value in options.items():
        if not value.strip():
            raise _setup_error(f'[{section}] has an option {key} with no value')


def _parse_bool(section: str, key: str, value: str) -> bool:
    if value.strip().lower() in _TRUE:
        return True
    if value.strip().lower() in _FALSE:
        return False
    raise _setup_error(f"[{section}] option {key} is '{value}', expected true or false")


def _parse_document(section: str, target: str, options: Mapping[str, str]) -> Document:
    _check_options(section, options, DOCUMENT_OPTIONS, 'nodl_file')
    if not target.isidentifier() or keyword.iskeyword(target):
        raise _setup_error(f"[{section}] target '{target}' is not a valid Python identifier")
    resource_name = options.get('resource_name', '').strip() or None
    index = not _parse_bool(section, 'no_index', options.get('no_index', 'false'))
    if not index and resource_name is not None:
        raise _setup_error(
            f"[{section}] is not registered with the ament index because of no_index, so resource_name '{resource_name}' has no effect. "
            'Remove one of them.'
        )
    if resource_name is not None and '/' in resource_name:
        raise _setup_error(f"[{section}] resource_name '{resource_name}' must not contain '/'")
    return Document(target, options['nodl_file'].strip(), resource_name, index)


def _parse_executable(section: str, name: str, options: Mapping[str, str]) -> Executable:
    _check_options(section, options, EXECUTABLE_OPTIONS, 'target')
    if '/' in name:
        raise _setup_error(f"[{section}] executable name '{name}' must not contain '/'")
    executor = options.get('executor')
    return Executable(name, options['target'].strip(), None if executor is None else executor.strip())


def parse_config(command_options: Mapping) -> Config:
    """Parse the nodl_generator_py sections from ``Distribution.command_options``.

    The references in executable sections are checked when the script is written.

    :param command_options: Mapping of section name to ``{option: (source, value)}``, as setuptools reads ``setup.cfg``.
    :raises DistutilsSetupError: When a section has no name, is incomplete, has an unknown option or an invalid value,
        or when two documents register the same resource name.
    """
    documents = tuple(
        _parse_document(section, name, options)
        for section, name, options in _sections(command_options, GENERATE_SECTION)
    )
    executables = tuple(
        _parse_executable(section, name, options)
        for section, name, options in _sections(command_options, EXECUTABLE_SECTION)
    )
    registered: dict[str, str] = {}
    for document in filter(lambda document: document.index, documents):
        if document.resource in registered:
            raise _setup_error(
                f"documents '{registered[document.resource]}' and '{document.target}' both register the resource name "
                f"'{document.resource}', resource names must be unique within a package. "
                'Set resource_name on one of them.'
            )
        registered[document.resource] = document.target
    return Config(documents, executables)


def project_dir(command_options: Mapping) -> Path:
    """Return the directory of the ``setup.cfg`` that the nodl_generator_py sections were read from.

    :raises DistutilsSetupError: When they were read from anything else, or from more than one file.
    """
    sources = {
        source
        for section, options in command_options.items()
        if _is_nodl_section(section)
        for source, _ in options.values()
    }
    if len(sources) != 1 or os.path.basename(next(iter(sources))) != 'setup.cfg':
        raise _setup_error(
            f'the nodl_generator_py sections must all be in one setup.cfg, but were read from {sorted(sources)}'
        )
    # setup.cfg is a symlink in the build space of a symlink install, so the project is where it really is.
    return Path(next(iter(sources))).resolve().parent


def check_runtime_dependency(package_xml: Path) -> str:
    """Return the package name from ``package_xml``, after checking that it declares a runtime dependency on nodl_runtime_py.

    Generated code imports what ``nodl_runtime_py`` provides, so a package without the dependency fails when it runs.
    """
    from catkin_pkg.package import InvalidPackage, parse_package

    try:
        package = parse_package(str(package_xml))
    except (InvalidPackage, OSError) as exc:
        raise _setup_error(f'cannot read {package_xml}: {exc}') from exc
    package.evaluate_conditions(os.environ)
    exec_depends = [depend.name for depend in package.exec_depends if depend.evaluated_condition is not False]
    if RUNTIME_PACKAGE not in exec_depends:
        raise _setup_error(
            f"package '{package.name}' must declare a runtime dependency on {RUNTIME_PACKAGE}, "
            'which generated code needs when it runs. '
            f'Add <exec_depend>{RUNTIME_PACKAGE}</exec_depend> to its package.xml.'
        )
    return package.name


def _generate_modules(documents: tuple[Document, ...], project: Path, generated_dir: Path) -> None:
    import yaml
    from jsonschema import ValidationError

    from nodl_generator_common.plan import CodegenError
    from nodl_generator_py.generator import generate_python, write_generation
    from nodl_schema.composition import MergeError, ResolutionError

    generated_dir.mkdir(parents=True)
    (generated_dir / '__init__.py').touch()
    for document in documents:
        source = project / document.nodl_file
        try:
            write_generation(generate_python(source, document.target), generated_dir, document.target)
        except (CodegenError, MergeError, ResolutionError, ValidationError, ValueError, yaml.YAMLError, OSError) as exc:
            raise _setup_error(f'{source}: {exc}') from exc


def _relative_files(directory: Path) -> list[str]:
    """List the files in ``directory`` relative to the working directory, as setuptools requires."""
    return [os.path.relpath(path) for path in sorted(directory.iterdir())]


def _register_documents(
    documents: tuple[Document, ...], package: str, project: Path, staging_dir: Path
) -> list[tuple[str, list[str]]]:
    """Stage the documents as ``ament_nodl_register`` installs them, and return them as ``data_files``.

    Each document is registered as ``nodl://<package>/<resource>``, and every ``local://`` include of a registered document is rewritten to that form.
    """
    from nodl_schema.rewrite import UnrewrittenReferenceError, rewrite_references

    registered = [(document, (project / document.nodl_file).resolve()) for document in documents if document.index]
    if not registered:
        return []
    by_path: dict[Path, str] = {}
    for document, path in registered:
        if path in by_path:
            raise _setup_error(
                f'{path} is already registered as {package}__{by_path[path]}, '
                'a file can be registered under only one name so local:// references to it rewrite unambiguously'
            )
        by_path[path] = document.resource
    rewrites = {f'local://{path}': f'nodl://{package}/{name}' for path, name in by_path.items()}

    index_dir = staging_dir / 'index'
    share_dir = staging_dir / 'share'
    index_dir.mkdir(parents=True)
    share_dir.mkdir(parents=True)
    for document, path in registered:
        try:
            text = rewrite_references(path, rewrites)
        except UnrewrittenReferenceError as exc:
            raise _setup_error(
                f'{package}__{document.resource} includes a local:// reference that is not registered.\n{exc}\n'
                'Register the included file with a nodl_generate_py.<target> section in the same package, '
                'so the reference can be rewritten to a nodl:// reference.'
            ) from exc
        (index_dir / f'{package}__{document.resource}').write_text(text)
        (share_dir / f'{document.resource}.nodl.yaml').write_text(text)
    return [
        ('share/ament_index/resource_index/nodl', _relative_files(index_dir)),
        (f'share/{package}/nodl', _relative_files(share_dir)),
    ]


def _write_scripts(executables: tuple[Executable, ...], scripts_dir: Path) -> list[str]:
    from nodl_generator_py.executable import executable_source

    scripts_dir.mkdir(parents=True)
    scripts = []
    for executable in executables:
        try:
            source = executable_source(executable.target, executable.executor)
        except ValueError as exc:
            raise _setup_error(f'[{EXECUTABLE_SECTION}.{executable.name}] {exc}') from exc
        path = scripts_dir / executable.name
        path.write_text(source)
        scripts.append(os.path.relpath(path))
    return scripts


def _console_script_names(dist) -> set[str]:
    entry_points = dist.entry_points or {}
    lines = entry_points.get('console_scripts', [])
    lines = lines.splitlines() if isinstance(lines, str) else lines
    return {line.partition('=')[0].strip() for line in lines if line.strip()}


def _check_script_names(dist, executables: tuple[Executable, ...]) -> None:
    taken = _console_script_names(dist) | {os.path.basename(script) for script in dist.scripts or []}
    for executable in executables:
        if executable.name in taken:
            raise _setup_error(
                f'[{EXECUTABLE_SECTION}.{executable.name}] installs a script that the package already installs, '
                'as a console_scripts entry or in scripts. Rename one of them.'
            )


def _package_dir(dist, package: str) -> Path:
    """Return the directory of ``package`` as setuptools sees it, relative to the working directory."""
    mapping = dist.package_dir or {}
    return Path(mapping[package] if package in mapping else os.path.join(mapping.get('', ''), package))


def _check_package(dist, package: str, source: Path) -> None:
    if package not in (dist.packages or []):
        raise _setup_error(
            f"generated modules install as '{package}.generated', but setup() does not list the package '{package}'"
        )
    if f'{package}.generated' in dist.packages or (source / 'generated').exists():
        raise _setup_error(
            f"the package '{package}' already has a 'generated' subpackage, "
            'but nodl_generator_py installs generated code as that subpackage. Rename it.'
        )


def _overlay_package_dir(package_dir: Path, generated_dir: Path) -> None:
    """Replace the symlink to the source package with a directory that links to its entries and to ``generated``.

    A ``colcon build --symlink-install`` puts the build space on ``PYTHONPATH``, where the package directory is a symlink to the source tree.
    Python finds ``<package>.generated`` through the directory that ``<package>`` was imported from,
    so the generated modules can only be found there by adding them to a directory that is not the source tree.
    """
    source = package_dir.resolve()
    package_dir.unlink()
    package_dir.mkdir()
    for entry in source.iterdir():
        if entry.name != '__pycache__':
            (package_dir / entry.name).symlink_to(entry)
    (package_dir / 'generated').symlink_to(generated_dir.resolve())


@dataclass(frozen=True)
class Generated:
    """What was configured: the package that may get a ``generated`` subpackage, and the executables as script files."""

    package: str
    scripts: list[str]


def _generate(cmd, develop: bool) -> Generated | None:
    dist = cmd.distribution
    config = parse_config(dist.command_options)
    if not (config.documents or config.executables):
        return None

    project = project_dir(dist.command_options)
    package = check_runtime_dependency(project / 'package.xml')
    _check_script_names(dist, config.executables)

    build = cmd.get_finalized_command('build')
    gen_root = Path(os.path.abspath(build.build_base)) / 'nodl_generated'
    shutil.rmtree(gen_root, ignore_errors=True)
    data_files: list[tuple[str, list[str]]] = []
    if config.documents:
        package_dir = _package_dir(dist, package)
        if develop and not package_dir.is_symlink():
            raise _setup_error(
                f'setup.py develop needs {package_dir} to be a symlink to the source package, as colcon --symlink-install makes it, '
                'because the generated modules cannot be written to the source tree. '
                'Build without --symlink-install, or build with colcon.'
            )
        _check_package(dist, package, package_dir.resolve())
        generated_dir = gen_root / package / 'generated'
        _generate_modules(config.documents, project, generated_dir)
        data_files = _register_documents(config.documents, package, project, gen_root / 'nodl')
        if develop:
            _overlay_package_dir(package_dir, generated_dir)
        else:
            dist.packages = [*dist.packages, f'{package}.generated']
            dist.package_dir = {**(dist.package_dir or {}), f'{package}.generated': os.path.relpath(generated_dir)}
    scripts = _write_scripts(config.executables, gen_root / 'scripts')
    dist.data_files = [*(dist.data_files or []), *data_files]
    if not develop:
        dist.scripts = [*(dist.scripts or []), *scripts]
    return Generated(package, scripts)


def generate_once(cmd, *, develop: bool = False) -> Generated | None:
    """Generate what ``setup.cfg`` configures, the first time a wrapped command of the distribution runs.

    :return: What ``setup.cfg`` configures, or ``None`` if it configures nothing.
    """
    dist = cmd.distribution
    if not hasattr(dist, _APPLIED):
        setattr(dist, _APPLIED, _generate(cmd, develop))
    return getattr(dist, _APPLIED)


def _install_develop_scripts(cmd, generated: Generated) -> None:
    """Install the executables as the scripts that an install makes.

    ``setup.py develop`` installs the scripts in ``scripts`` as wrappers that import ``pkg_resources`` when they start.
    The generated scripts import the package normally, so a develop install copies them as they are.
    """
    script_dir = Path(cmd.script_dir or cmd.install_dir)
    for script in generated.scripts:
        target = script_dir / Path(script).name
        if not cmd.dry_run:
            script_dir.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            shutil.copy(script, target)
            target.chmod(0o755)


def _sync_build_py(cmd, generated: Generated) -> None:
    # An earlier build leaves the modules of documents that are no longer configured, which the install would copy.
    shutil.rmtree(Path(cmd.build_lib) / generated.package / 'generated', ignore_errors=True)
    cmd.finalize_options()


def _sync_build_scripts(cmd, generated: Generated) -> None:
    cmd.finalize_options()


def _sync_data_files(cmd, generated: Generated) -> None:
    cmd.data_files = cmd.distribution.data_files


# What each wrapped command refreshes from the distribution, after the first command generated into it.
# Commands that are created before that, for example because they are on the command line, hold what the distribution had then.
_COMMANDS = {
    'build': None,
    'build_py': _sync_build_py,
    'build_scripts': _sync_build_scripts,
    'install': None,
    'install_data': _sync_data_files,
    'symlink_data': _sync_data_files,
    'develop': None,
    'editable_wheel': None,
}


def _wrap(base, sync, develop: bool, editable: bool):
    class Wrapped(base):
        def run(self):
            if editable:
                _refuse_editable(self.distribution)
            generated = None if develop and getattr(self, 'uninstall', False) else generate_once(self, develop=develop)
            if generated is not None and sync is not None:
                sync(self, generated)
            super().run()
            if develop and generated is not None:
                _install_develop_scripts(self, generated)

    Wrapped.__name__ = base.__name__
    Wrapped.__qualname__ = base.__qualname__
    Wrapped.__doc__ = base.__doc__
    Wrapped._nodl_generator_py_wrapped = True
    return Wrapped


def _refuse_editable(dist) -> None:
    """Refuse an editable install of a configured package, before anything is generated."""
    config = parse_config(dist.command_options)
    if config.documents or config.executables:
        raise _setup_error(
            'an editable install cannot import the generated modules, because they cannot be written to the source tree. '
            'Install the package, or build with colcon --symlink-install.'
        )


def _is_configured(dist) -> bool:
    """Return whether any configuration file has a nodl_generator_py section."""
    for name in dist.find_config_files():
        try:
            text = Path(name).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        if _SECTION.search(text):
            return True
    return False


def _can_wrap(name: str, base) -> bool:
    """Return whether ``base`` can be wrapped.

    From setuptools 80, ``develop`` only runs ``pip install -e``, and has no ``uninstall`` option for the wrapper to honour.
    """
    if getattr(base, '_nodl_generator_py_wrapped', False):
        return False
    return name != 'develop' or any(
        option[0].rstrip('=') == 'uninstall' for option in getattr(base, 'user_options', [])
    )


def install_commands(dist) -> None:
    """``setuptools.finalize_distribution_options`` hook: wrap the commands that build and install the package.

    This does nothing unless a configuration file has a nodl_generator_py section.
    ``symlink_data`` is colcon's command for a symlink install, and ``editable_wheel`` is setuptools' for an editable install from 64,
    so each is only wrapped when it is available.
    """
    from distutils.errors import DistutilsModuleError

    if not _is_configured(dist):
        return
    for name, sync in _COMMANDS.items():
        try:
            base = dist.get_command_class(name)
        except DistutilsModuleError:
            continue
        if _can_wrap(name, base):
            dist.cmdclass[name] = _wrap(base, sync, develop=name == 'develop', editable=name == 'editable_wheel')
