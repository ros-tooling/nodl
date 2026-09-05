# nodl_generator_common

`nodl_generator_common` holds the language-agnostic core of the NoDL code generators.
A generator becomes "a config model + a schema + templates + a type mapping" and reuses this package for everything else.

## Modules

- `provenance` — the include-tree barrier walk (`build_provenance_map`) and entity filtering (`filter_provided_entities`),
  keyed by `EntityKey`. The walk takes an extractor callback that returns a document's parsed language config, or `None`;
  the first document carrying config on each branch is a *barrier* that owns its whole subtree.
- `generated_file` — the `GeneratedFile(filename, content)` dataclass every generator emits.
- `ament_deps` — ament package extraction from ROS interface types and the `<target>_deps.cmake` writer.
- `naming` — language-agnostic name-case conversions (`camel_to_snake`, `snake_to_pascal`, `to_member_name`).

## Relationship to other packages

A generator such as `nodl_generator_cpp` keeps its own config model, JSON schema, templates, and type mapping,
and passes a thin adapter selecting its `codegen.<lang>` key into `build_provenance_map`.
The shared core stays generic so a second generator (Python, Rust, …) reuses it instead of re-implementing the include-tree analysis.
