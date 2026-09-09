# nodl_generator_common

`nodl_generator_common` holds the language-agnostic core of the NoDL code generators.
A generator becomes "a config model + a schema + templates + a type mapping" and reuses this package for everything else.

## Modules

- `provenance` — the include-tree barrier walk (`build_provenance_map`) and entity filtering (`filter_provided_entities`),
  keyed by `EntityKey`. The walk takes an extractor callback that returns a document's parsed language config, or `None`;
  the first document carrying config on each branch is a *barrier* that owns its whole subtree.
  `resolve_provenance(source, extract_config)` is the one-call entry point most generators want:
  it loads the document, walks provenance, and filters entities, returning a `ResolvedProvenance`
  with the `barriers`, the surviving `entities`, and the resolved `sources` (the document plus its includes).
  The three primitives stay public for generators that need finer control.
- `generated_file` — the `GeneratedFile(filename, content)` dataclass every generator emits.
- `naming` — language-agnostic name-case conversions (`camel_to_snake`, `to_member_name`).

## Writing a generator

This section is the guide for authoring a new target-language generator (Python, Rust, …).
`nodl_generator_cpp` is the reference implementation; file references below point into it.

### What a generator does, end to end

A generator turns one NoDL document into a set of source files for a target language.
Everything from parsing to include resolution to provenance is shared;
the generator supplies only the language-specific pieces.

`nodl_generator_common` provides shared implementations of parts of this pipeline. Each step below is either marked **(common)** or **(generator)**.

1. **Parse the CLI** — **(generator)**
   The generator owns its command line: the NoDL source, an output directory, a target name, and any language options.
   See `cli.py` / `__main__.py`. The generator manages this because the cli is the main interface for build-system integration.

2. **Load and resolve the document** — **(common)**
   `resolve_provenance(source, extract_config)` loads the document and its include tree (via the `nodl_schema` loader),
   walks the tree for provenance, filters entities, and returns a `ResolvedProvenance`
   (`barriers`, the `entities` to scaffold, and the resolved `sources`).
   Steps 2a–2c happen inside this one call.

   - 2a. **Detect barriers** — **(generator predicate, common walk)**
     The walk calls the generator's `extract_config` predicate on each document.
     This pure `NodlDocument -> Optional[Config]` selects and parses the generator's `codegen.<lang>` key,
     returning `None` when the document carries none.
     A document for which it returns non-`None` is a *barrier* that owns its whole subtree.
     That predicate *is* the definition of a barrier for your language; it is the only thing the core needs from you.

   - 2b. **Attribute and filter entities** — **(common)**
     Every entity behind a barrier is already implemented by a base or dependency, so the core filters it out;
     what remains in `entities` is exactly what the generator must scaffold.

   - 2c. **Collect sources** — **(common)**
     The resolved root path plus every transitive include, for build-system file watching.

3. **Validate language policy** — **(generator)**
   The core never rejects a document; whether the resolved barriers form a *valid* target for your language is your rule
   (e.g. how many barriers of a given role are allowed, which are required, which combinations conflict),
   raised as your own error type.

4. **Map ROS-domain values to the target language** — **(generator)**
   Convert interface types, QoS, and names into finished language strings with pure, doctested functions
   (`ros_to_cpp.py`). Language-agnostic name conversions are reused from `nodl_generator_common.naming` (`camel_to_snake`, `to_member_name`); language-specific ones stay local (e.g. `to_class_name`).

5. **Build the template context and render** — **(generator)**
   Assemble a flat context of already-converted strings in one place and render the templates.
   Templates should contain no conversion logic.

6. **Return generated files** — **(common type, generator content)**
   Rendering returns `list[GeneratedFile]` (`GeneratedFile(filename, content)` from `generated_file`).
   The core produces data, not side effects.

7. **Write to disk** — **(generator)**
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

A generator such as `nodl_generator_cpp` keeps its own config model, JSON schema, templates, and type mapping,
and passes a thin adapter selecting its `codegen.<lang>` key into `build_provenance_map`.
The shared core stays generic so a second generator (Python, Rust, …) reuses it instead of re-implementing the include-tree analysis.
