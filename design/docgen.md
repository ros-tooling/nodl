# NoDL documentation generation

This describes the "Document" stage of the roadmap:
producing rosdoc2-compatible node interface documentation from registered NoDL documents.

## Goals

1. A package author can render their NoDL document(s) into their package's rosdoc2 docs with a few lines of configuration.
2. The rendered page can never drift from the NoDL source, because rendering happens at Sphinx build time.
3. The rendering logic is a pure, testable core, usable outside Sphinx (CLI, README generation) later.

## Prior art: generate_parameter_library

`generate_parameter_library_markdown` is a standalone CLI whose markdown output authors paste into a README.
The good idea is generating docs from the single source of truth.
The failure mode is paste-time generation: output goes stale, and there is no rosdoc2 integration.
This design inverts it: render inside the package's normal Sphinx/rosdoc2 build, from the same file that `ament_nodl_register` registers.
NoDL's parameter schema is borrowed from `generate_parameter_library`,
so its parameter rendering conventions (constraint sentences for validators) carry over to the parameters section.

## Constraints

- On the buildfarm, rosdoc2 builds a package's docs from source with its dependencies installed, but not the package itself.
  A package documenting its own NoDL therefore cannot go through the ament index;
  it must load the source file by path.
  `nodl://` includes that point at dependencies still resolve through the installed index.
- The output must work in both MyST and rst projects, and under warnings-as-errors.
- A NoDL document has no name field; identity lives in the registration key.
  The rendered title must come from the doc author (or a filename fallback).

## Design: `nodl_sphinx` package

A new ament_python package at the repo root, following the a-la-carte package structure.
The name `nodl_docs` is taken by the combined doc site's editable install,
and `nodl_sphinx` follows the ecosystem convention for Sphinx extension packages.
The `nodl` metapackage adds it as a dependency.

Three layers, with all real logic in the bottom one:

### 1. `summarize.py`: pure summary core

Pure functions from a resolved `nodl_schema.loader.DocumentTree` (or a bare `NodlDocument`) to a presentation-neutral summary:
a `NodeSummary` dataclass holding the description, the list of include refs,
and per-section tables (parameters, publishers, subscriptions, service servers/clients, action servers/clients) as typed rows of plain strings.
This layer owns the formatting decisions:
QoS profiles compressed to a readable summary string (omitting SYSTEM_DEFAULT fields),
parameter validators rendered as constraint sentences (GPL-style),
default values rendered as YAML literals.
No Sphinx or docutils imports.
Usable and golden-testable from a REPL with no knowledge of the larger system.

### 2. `directives.py`: the `nodl-node` directive

Turns a `NodeSummary` into docutils nodes (sections, tables, paragraphs).
Emitting docutils nodes rather than nested-parsing generated markdown makes the directive work identically from MyST and rst sources,
since docutils is Sphinx's own intermediate representation.

Directive contract:

- One required argument: a path to the NoDL file, relative to the containing doc source file,
  with a leading `/` meaning the Sphinx source root (literalinclude semantics).
  Alternatively a `nodl://<package>/<name>` reference, resolved via the ament index, for documenting installed dependencies.
- By default the document is fully resolved and merged (`resolve_document` + `merge_documents`),
  rendering the complete effective interface, with an "Includes" note listing the direct include refs.
- `:title:` option sets the section heading; the default is the file stem (or `<package>/<name>` for index refs).
- A table drops any column no row fills in, so a table of services that declare no QoS profile carries no QoS column.
  Name and Type always stay, since they are what a reader looks a row up by.
- Load or validation failures raise a docutils directive error carrying the directive's source location,
  which Sphinx reports as a warning against that line,
  so broken NoDL fails the doc build under warnings-as-errors rather than rendering half a page.
- The NoDL file (and every file it includes) is registered as a build dependency (`env.note_dependency`),
  so incremental Sphinx rebuilds pick up edits.

### 3. `__init__.py`: extension setup

Registers the directive and declares the extension parallel-read safe.

## Author workflow

This is the entire integration surface, and the substance of the how-to guide:

1. `package.xml`: `<doc_depend>nodl_sphinx</doc_depend>`
2. `doc/conf.py`: add `'nodl_sphinx'` to `extensions`
3. In a doc page:

   ````markdown
   ```{nodl-node} /../nodl/my_node.nodl.yaml
   :title: my_node
   ```
   ````

## Testing

- Golden tests for the summary core: NoDL fixture in, expected `NodeSummary` out.
  These are plain pytest, no ROS or Sphinx runtime needed beyond `nodl_schema`.
- Directive tests with `sphinx.testing` fixtures:
  build a minimal project containing the directive, assert on the doctree and on error behavior for invalid input.
- The repo's standard `test_pyright.py` type check.

## Documentation deliverables

- A top-level guide `nodl/doc/documenting.md` ("Documenting your node's interface"):
  the three-step workflow above, dogfooded by rendering a real NoDL fixture live in the combined site so readers see actual output.
- `nodl_sphinx` package docs per `design/docs.md`:
  `doc/overview.md` + `doc/conf.py`, `rosdoc2.yaml`, entries in `PACKAGES`/toctree, and the CI matrix.
- Repo `README.md` structure entry and `roadmap.md` update.

## Phasing

Each phase is a standalone, reviewable diff:

1. Package scaffold + `summarize.py` + golden tests.
2. `nodl-node` directive + extension setup + Sphinx-level tests.
3. Documentation: author guide, package overview, combined-site and CI integration.

## Follow-ups in nodl_schema

Rough edges the directive works around, better fixed where they live:

- A `DocumentTree` records the refs it resolved but not the paths it resolved them to,
  so `directives.py`'s `include_paths()` resolves every ref a second time to collect the build dependencies.
- The pydantic `Validation` model forbids the namespace-qualified custom validators the JSON schema allows,
  so a parameter using one passes schema validation and then fails to load.
- `load_nodl_with_doc_tree` merges the tree and `summarize_tree` merges it again,
  so the directive asks for a merged document and throws it away.

## Deferred

- `ros2 nodl document` CLI verb emitting plain markdown for READMEs (GPL parity).
  Reuses the summary core with a small markdown emitter.
- A `nodl-package` directive that auto-documents every registered NoDL of an installed package,
  useful for umbrella or fleet-level sites.
- Hyperlinking message types to docs.ros.org interface pages.
  Needs a distro/base-URL config knob; plain code spans until then.
- Upstream rosdoc2 support that emits an interfaces page with zero author edits.
  The extension is the stepping stone; requires an upstream conversation.
