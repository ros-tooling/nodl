# nodl_docgen

`nodl_docgen` is a Sphinx extension that renders a NoDL document into a documentation page at build time.
It provides one directive, `nodl-node`, which reads a NoDL file and emits the node's interface as prose and tables.

Because the rendering happens during the doc build, the page cannot drift from the NoDL source:
the file that describes the node is the file the page is drawn from,
and a document that no longer loads becomes a build error rather than a stale page.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.
This page documents the extension's surface.

% The authoring guide is linked by URL rather than through the nodl intersphinx inventory,
% which only holds pages that are already published:
% an {external+nodl:doc} reference to a page added in the same change fails the combined build.

The authoring walkthrough, with a rendered example, is
[Documenting your node's interface](https://nodl.readthedocs.io/en/latest/documenting.html).

## Enabling the extension

These edits, in the package whose docs should carry the rendering:

1. Declare the dependency in `package.xml`, so the buildfarm installs the extension for the doc build:

   ```xml
   <doc_depend>nodl_docgen</doc_depend>
   ```

2. Enable it in the package's `doc/conf.py`:

   ```python
   extensions = [
       'myst_parser',
       'nodl_docgen',
   ]
   ```

3. Use the directive in a page:

   ````markdown
   ```{nodl-node} /../nodl/my_node.nodl.yaml
   :title: my_node
   ```
   ````

## The `nodl-node` directive

### Argument

The single required argument names the document to render, in one of two forms.

A **path** is resolved the way `literalinclude` resolves one:
relative to the page containing the directive, or relative to the Sphinx source root when it starts with `/`.
A package's own NoDL files usually sit outside `doc/`, so the path leaves the doc tree:
`/../nodl/my_node.nodl.yaml` from a `doc/` at the package root.

A **reference** is a URI handled by one of `nodl_schema`'s registered resolvers.
`nodl://<package>/<name>` resolves through the ament index,
which is how a page documents a node it does not ship but depends on.
`local://<relative path>` resolves relative to the page, like a plain path.

Use a path for your own package's documents.
`rosdoc2` builds a package from source with its dependencies installed but not the package itself,
so a package's own NoDL is not in the ament index at the time its docs are built.
References are for documents that come from somewhere else.

### Options

`:title:` sets the heading of the rendered section.
Without it the heading is derived from the argument:
a path becomes its filename with the `.nodl`, `.yaml`, `.yml`, and `.json` suffixes stripped,
so `my_node.nodl.yaml` becomes `my_node`,
and a reference becomes itself without its scheme, so `nodl://sensor_common/imu` becomes `sensor_common/imu`.

A NoDL document has no name field, since a node's identity comes from the package that registers it,
so the heading is the author's to choose.

### What it renders

The directive emits one section, titled as above, holding:

- the document's `description`, one paragraph per blank-line-separated block,
- a note listing the direct `include` references, when the document has any,
- one subsection per interface category that has entries, in a fixed order:
  Parameters, Publishers, Subscriptions, Service Servers, Service Clients, Action Servers, Action Clients.

Each subsection is a table of that category's entries, in document order.
A document that declares nothing renders as a bare titled section, rather than as a page of empty tables.

Includes are resolved and merged before rendering,
so the tables are the node's whole effective interface, not just the part written in this file.
The note names where the rest came from.

A column that no row fills in is dropped:
a table of service servers that declare no QoS profile carries no QoS column.
Name and Type always stay, since they are what a reader looks a row up by.

Values are rendered the way an author writes them:
a parameter default is a YAML literal (`true`, `[1.0, 2.0]`),
and an empty Default cell means the parameter has no default and must be set at startup.
A parameter's validators become constraint sentences in its Description cell ("must be greater than 0.0"),
the convention `generate_parameter_library` uses in the markdown it generates.
A QoS profile collapses to one line naming only what differs from the system default,
so `KEEP_LAST(5), BEST_EFFORT` is a profile whose remaining policies are all defaults.
A parameter name containing `__map_<key>` is shown as `<key>`,
since a mapped parameter stands for one parameter per runtime key.

Descriptions are rendered as plain text.
Markup written in a NoDL description is not interpreted,
because a description is prose that other NoDL consumers render too, not Sphinx markup.

Several nodes can be documented on one page.
Each rendered section gets its own identifier, so headings do not collide.

### Failures

A document that cannot be loaded, validated, resolved, or merged raises a directive error,
carrying the directive's own source location.
Sphinx reports it as a warning against that line,
and a doc build run with `-W` fails there rather than publishing a page that documents less than the node does.

### Rebuilds

The document and every file it includes are registered as build dependencies of the page.
An incremental `sphinx-build` therefore re-renders the page when a NoDL file it draws from changes.

## The summary core

The formatting decisions live in `nodl_docgen.summarize`, which is pure:
it maps a `nodl_schema` document tree to a `NodeSummary` of plain strings, with no Sphinx or docutils imports.

```python
from pathlib import Path

from nodl_schema import load_nodl_with_doc_tree
from nodl_docgen.summarize import summarize_tree

_, tree = load_nodl_with_doc_tree(Path('my_node.nodl.yaml').resolve())
summary = summarize_tree(tree)
print(summary.parameters)
```

`nodl_docgen.directives` turns a `NodeSummary` into docutils nodes.
Emitting nodes rather than nested-parsing generated markdown is what makes the directive behave identically in MyST and in reStructuredText sources,
since docutils is Sphinx's own intermediate representation.

## Relationship to other packages

`nodl_docgen` loads and resolves documents with `nodl_schema`, and inherits its `include` handling,
so a `nodl://` reference points at a document that `ament_nodl` registered.
The extension reads NoDL from a path or the ament index only;
it does not observe a running node, which is what `nodl_observe` and `ros2nodl` do.
