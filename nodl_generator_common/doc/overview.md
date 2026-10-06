# nodl_generator_common

`nodl_generator_common` holds the language-agnostic core of the NoDL code generators.
A generator becomes "a config model + a schema + templates + a type mapping" and reuses this package for everything else.

## Modules

- `generated_file` — the `GeneratedFile(filename, content)` dataclass every generator emits.
- `naming` — language-agnostic name-case conversions (`camel_to_snake`, `to_member_name`).
- `parameters` — expansion of flat dotted NoDL parameter names into nested generator input mappings.

## Writing a generator

This section is the guide for authoring a new target-language generator (Python, Rust, …).
`nodl_generator_cpp` is the reference implementation; file references below point into it.

### What a generator does, end to end

A generator turns one NoDL document into a set of source files for a target language.
Parsing and include resolution are shared through `nodl_schema`;
the generator decides what it generates and supplies the language-specific pieces.

`nodl_generator_common` provides shared implementations of parts of this pipeline. Each step below is either marked **(common)** or **(generator)**.

1. **Parse the CLI** — **(generator)**
   The generator owns its command line: the NoDL source, an output directory, a target name, and any language options.
   See `cli.py` / `__main__.py`. The generator manages this because the cli is the main interface for build-system integration.

2. **Load and resolve the document** — **(`nodl_schema`)**
   `nodl_schema.loader.load_nodl_with_doc_tree(source)` loads and validates the document,
   resolves its include tree, and returns the merged document alongside the unmerged `DocumentTree`.
   Merging the whole tree reports name collisions anywhere in it.
   The tree's `included_paths()` plus the source are the files the build system watches.

3. **Walk the tree and decide what to generate** — **(generator)**
   Walk the `DocumentTree` and read your `codegen.<lang>` key on each included document.
   Its schema and roles are yours, so the walk is too:
   it decides which documents you generate, which already have an implementation (and whether to look inside them),
   and what each contributes, such as a base class.
   Merge the documents you generate with `nodl_schema.composition.merge_documents`.
   See `_plan_tree` in `nodl_generator_cpp/generate.py`.

4. **Validate language policy** — **(generator)**
   Whether what the walk found forms a *valid* target for your language is your rule
   (e.g. how many providers of a given role are allowed, which are required, which combinations conflict),
   raised as your own error type.

5. **Map ROS-domain values to the target language** — **(generator)**
   Convert interface types, QoS, and names into finished language strings with pure, doctested functions
   (`ros_to_cpp.py`). Language-agnostic name conversions are reused from `nodl_generator_common.naming` (`camel_to_snake`, `to_member_name`); language-specific ones stay local (e.g. `to_class_name`).

6. **Build the template context and render** — **(generator)**
   Assemble a flat context of already-converted strings in one place and render the templates.
   Templates should contain no conversion logic.

7. **Return generated files** — **(common type, generator content)**
   Rendering returns `list[GeneratedFile]` (`GeneratedFile(filename, content)` from `generated_file`).
   The core produces data, not side effects.

8. **Write to disk** — **(generator)**
   Only the CLI/build glue touches the filesystem, writing each `GeneratedFile` into the output directory.

### Principles that fall out of this

- **Return data, never write files from the core.**
  The generation core returns `GeneratedFile`s; only the CLI writes them.
  This keeps the core usable and testable from a shell or REPL with no knowledge of the larger build system.

- **The `codegen.<lang>` schema is the single source of truth.**
  It is opaque to `nodl_schema`: its schema and meaning are owned entirely by the generator.
  Ship a JSON schema, validate against it in your loader, and generate the config model from it
  rather than hand-writing a second copy of the same contract (e.g. `datamodel-codegen` to produce `models.py` from the schema).

- **Keep templates dumb; pre-convert in the context builder.**
  Render with strict, fail-loud settings (e.g. `StrictUndefined` with `trim_blocks`/`lstrip_blocks`) so a missing value is an error, not silent empty output.

- **Make the type mapping pure and doctested.**
  The smell test: each conversion is callable and verifiable from a REPL on its own.

- **Put policy in the generator, not the core.**
  Different target languages disagree on validity rules, so encoding any of them in the core
  would leak one language's policy into all the others.

- **Make output deterministic.**
  Generated files are never hand-edited — they are regenerated whenever the NoDL source changes.
  Sort and deduplicate anything with no inherent order (includes, dependency lists) so output is stable;
  this is what makes golden tests reliable and keeps rebuilds from churning.

- **Test with goldens.**
  Drive end-to-end tests from `test/golden/<case>/input.nodl.yaml` to a checked-in `expected/` tree.
  A golden case per feature (publishers, services, actions, parameters, inheritance, …) doubles as executable documentation.

## Relationship to other packages

A generator such as `nodl_generator_cpp` keeps its own config model, JSON schema, templates, type mapping,
and the walk over the include tree that interprets its `codegen.<lang>` roles.
This package holds only what is identical across languages.
