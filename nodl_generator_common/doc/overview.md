# nodl_generator_common

`nodl_generator_common` holds the language-agnostic core of the NoDL code generators.
A generator becomes "a config model + a schema + templates + a type mapping" and reuses this package for everything else.

## Modules

- `generated_file` — the `GeneratedFile(filename, content)` dataclass every generator emits.
- `naming` — language-agnostic name-case conversions (`camel_to_snake`, `to_member_name`).
- `parameters` — expansion of flat dotted NoDL parameter names into nested generator input mappings.
- `plan` — the document tree walk (`plan`, `walk_tree`), driven by a generator's `CodegenSchema` and `CodegenPlanner`.

## Writing a generator

This section is the guide for authoring a new target-language generator (Python, Rust, …).
`nodl_generator_cpp` is the reference implementation; file references below point into it.

### Generation process

A generator turns one NoDL root document into a set of source files for a target language.
Parsing and include resolution are shared through `nodl_schema`;
the generator decides what it generates and supplies the language-specific pieces.

`nodl_generator_common` provides shared implementations of parts of this pipeline.

1. **Parse the CLI**
   The generator owns its command line: the NoDL source, an output directory, a target name, and any language options.
   See `cli.py` / `__main__.py`. The generator manages this because the cli is the main interface for build-system integration.

1. **Plan what to generate**
   `plan(source, codegen, planner)` loads and validates the document, resolves its include tree,
   and walks the tree breadth-first from the root.
   It returns a `CodegenPlan`: the merged document to generate, and the source files the build system watches.

   The generator supplies the rest:
   - A `CodegenSchema`: its `codegen.<lang>` key, the JSON schema file for it, and a `parse` function into a typed model.
     `parse` may raise `jsonschema.ValidationError` for checks the schema cannot express.
   - A `CodegenPlanner`, which receives each reached document's parsed config.
     `root` sees the root document, which is always generated.
     `visit` sees each included document and returns `Walk.CONTINUE` to generate it and walk into its includes,
     or `Walk.STOP` to do neither.
     `finalize` checks what the walk found against the language's rules
     (e.g. how many documents of a given role are allowed, which are required, which combinations conflict),
     raising the generator's own error type, and completes the planner's results, such as the base class.
     The generator reads those from the planner after `plan` returns.

   See `CppPlanner` in `nodl_generator_cpp/generate.py`.

1. **Map ROS-domain values to the target language**
   Convert interface types, QoS, and names into finished language strings with pure, doctested functions
   (`ros_to_cpp.py`). Language-agnostic name conversions are reused from `nodl_generator_common.naming` (`camel_to_snake`, `to_member_name`); language-specific ones stay local (e.g. `to_class_name`).

1. **Build the template context and render**
   Assemble a flat context of already-converted strings in one place and render the templates.
   Templates should contain no conversion logic.

1. **Return generated files**
   Rendering returns `list[GeneratedFile]` (`GeneratedFile(filename, content)` from `generated_file`).
   The core produces data, not side effects.

1. **Write to disk**
   Only the CLI/build glue touches the filesystem, writing each `GeneratedFile` into the output directory.

### Design Principles

- **Return data, never write files from the generator implementation.**
  The generator library returns `GeneratedFile`s, only the interface (CLI, build glue) writes them.
  This keeps the core logic flexible and testable.

- **The `codegen.<lang>` schema is the single source of truth.**
  This subschema is owned by the generator, its contents are opaque to `nodl_schema`.
  Ship a JSON schema, validate against it in your loader, and generate the config model from it.

- **Keep templates dumb; pre-convert in the context builder.**
  Render with strict, fail-loud settings (e.g. `StrictUndefined` with `trim_blocks`/`lstrip_blocks`) so a missing value is an error, not silent empty output.

- **Make output deterministic.**
  Generated files are never hand-edited — they are regenerated whenever the NoDL source changes.
  Sort and deduplicate anything with no inherent order (includes, dependency lists) so output is stable.

- **Test with goldens.**
  Drive end-to-end tests from `test/golden/<case>/input.nodl.yaml` to a checked-in `expected/` tree.
  A golden case per feature (publishers, services, actions, parameters, inheritance, …) doubles as executable documentation.

## Relationship to other packages

A generator such as `nodl_generator_cpp` keeps its own config model, JSON schema, templates, type mapping,
and the walk over the include tree that interprets its `codegen.cpp` roles.
This package holds only what is identical across languages.
