# Editor setup

NoDL works with schema-aware YAML editors, including VS Code with the [Red Hat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) and other [YAML Language Server](https://github.com/redhat-developer/yaml-language-server) clients.
The schema provides field completion, enum suggestions, hover documentation, and inline validation.
No ROS installation or custom NoDL extension is required for these editor features.

## VS Code

Install the Red Hat YAML extension.
Copy the following settings into your workspace's `.vscode/settings.json`, merging `yaml.schemas` if you already associate other schemas:

```{literalinclude} ../../tools/editor/examples/settings.json
:language: json
```

The patterns match `*.nodl.yaml` and `*.nodl.yml` in the workspace root and nested directories.
Open a NoDL file and use completion (Ctrl+Space) to explore fields and values.
Hover over `nodl_version` to see its description.

For example, this document has no schema diagnostics:

```{literalinclude} ../../tools/editor/examples/valid.nodl.yaml
:language: yaml
```

This intentionally invalid document reports an unknown field, an unsupported parameter type (`float`), and a missing QoS `depth` for `KEEP_LAST`:

```{literalinclude} ../../tools/editor/examples/invalid.nodl.yml
:language: yaml
```

## Other YAML Language Server clients

Pass the same `yaml.schemas` mapping in your client's YAML settings.
The client must enable schema validation, completion, and hover (enabled by default in VS Code).
Alternatively, associate a single document with a comment at the top:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/ros-tooling/nodl/main/nodl_schema/nodl_schema/schemas/nodl.schema.json
nodl_version: 2
```

Use the comment form; a top-level `$schema` field is not part of the NoDL document contract.

## Published schemas and offline use

The stable [NoDL JSON Schema URL](https://raw.githubusercontent.com/ros-tooling/nodl/main/nodl_schema/nodl_schema/schemas/nodl.schema.json) tracks `main`.
Its relative reference loads the colocated [parameter schema](https://raw.githubusercontent.com/ros-tooling/nodl/main/nodl_schema/nodl_schema/schemas/parameter.schema.json).
Replace `main` in the URL with a release tag or commit containing the JSON files to pin a version.
These URLs become available when this change merges to `main`.

For offline use, download both JSON files into the same directory and replace the URL in `yaml.schemas` with the local path to `nodl.schema.json`.
Installed `nodl_schema` packages also include both JSON files alongside their YAML sources.
If an editor reports that a schema cannot load, check network access or use the local files.

Editor validation checks the JSON Schema contract.
It does not resolve NoDL includes, inspect installed ROS types, or apply NoDL's additional parameter semantic checks.
Use NoDL tooling for those checks; see the {doc}`schema` reference and {doc}`tutorials/basics`.

## Maintaining the integration

The YAML schemas are canonical.
Regenerate their JSON copies from the repository root after changing a schema:

```bash
python3 tools/editor/export_schemas.py --output nodl_schema/nodl_schema/schemas nodl_schema/nodl_schema/schemas/nodl.schema.yaml nodl_schema/nodl_schema/schemas/parameter.schema.yaml
```

The exporter requires PyYAML.
Pre-commit also regenerates these files, and CI checks that they are current.
Run the editor checks with Node.js 22:

```bash
npm ci --ignore-scripts --prefix tools/editor
npm test --prefix tools/editor
```

The tests use YAML Language Server's actual language service and the settings and fixtures shown above.
They serve local JSON contents at the published URLs to check relative references without a network dependency.
