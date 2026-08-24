# Documenting your node's interface

A node's NoDL document already states its parameters, topics, services, and actions.
The `nodl_docgen` extension renders that document into your package's documentation while the docs are being built,
so the interface page is generated from the same file the rest of the toolchain reads.

Nothing is pasted, so nothing goes stale.
If the document changes, the page changes with it.
If the document stops loading, the build reports an error at the directive,
rather than publishing a page that no longer matches the node.

This page is the authoring walkthrough.
For the directive's full option surface, see the
{doc}`nodl_docgen package page <_generated/packages/nodl_docgen/overview>`.

## 1. Depend on the extension

`nodl_docgen` is only needed when documentation is built, which is what `doc_depend` means:

```xml
<doc_depend>nodl_docgen</doc_depend>
```

## 2. Enable the extension

Add it to `extensions` in your package's `doc/conf.py`:

```python
extensions = [
    'myst_parser',
    'nodl_docgen',
]
```

## 3. Render the document

Point the `nodl-node` directive at the NoDL file:

````markdown
```{nodl-node} /../nodl/my_node.nodl.yaml
:title: my_node
```
````

The same directive in a reStructuredText page:

```rst
.. nodl-node:: /../nodl/my_node.nodl.yaml
   :title: my_node
```

The argument is a path, resolved like `literalinclude` resolves one:
relative to the page, or relative to the Sphinx source root when it starts with `/`.
NoDL files usually live outside `doc/`, hence the `/../nodl/...` above,
which climbs out of a `doc/` directory at the package root.

Use a path, not a `nodl://` reference, for your own package's documents.
`rosdoc2` builds a package's docs from source with its dependencies installed but not the package itself,
so a package's own NoDL is not yet in the ament index while its docs are being built.
A `nodl://<package>/<name>` reference is for documenting a node that comes from a dependency.

`:title:` is the heading, and is worth setting:
a NoDL document carries no name of its own, because a node's identity comes from the package that registers it.

## A rendered example

This site dogfoods the directive.
The document below is checked in at {repo}`nodl/doc/examples/battery_monitor.nodl.yaml`:

```{literalinclude} examples/battery_monitor.nodl.yaml
:language: yaml
```

Rendered by pointing the directive at that file, with `:title: battery_monitor`:

```{nodl-node} examples/battery_monitor.nodl.yaml
:title: battery_monitor
```

## Reading the output

A few things in that rendering are worth pointing out, because they are decisions rather than a straight field dump:

- Each interface category that has entries becomes a subsection with a table,
  and one that has none is left out entirely.
- A column no row fills in is dropped.
  The service server above declares no QoS profile, so its table has no QoS column, while the topic tables do.
- A QoS profile is summarized in one line, naming only what differs from the system default.
- A parameter's validators are read out as constraint sentences,
  and its default is shown as the YAML literal you would write in a parameter file.
  An empty default means the parameter has none and has to be set at startup, like `cell_count` above.

Descriptions are rendered as plain text.
Write them as prose rather than as markup: they are read by every NoDL consumer, not only by Sphinx.

## Next steps

- {doc}`concepts` covers what a NoDL document declares.
- {doc}`schema` is the field-by-field reference for writing one.
- The {doc}`nodl_docgen page <_generated/packages/nodl_docgen/overview>` documents the directive's argument forms,
  options, `include` merging, failure behavior, and the summary core underneath it.
