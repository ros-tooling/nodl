# Documentation design

This describes how the NoDL documentation is structured and built at a high level.

## Goals

1. Every shipped package is documented the way `docs.ros.org` expects, so it builds in the buildfarm with no changes.
2. There is a combined site (`nodl.readthedocs.io`) for the pre-release period, since the buildfarm has no single site we control.

Both must be served from a single set of sources authored inside each package, so there is one place to edit and no copies to keep in sync.

## Source layout

Each documented package owns a small `doc/` tree next to its code:

```
<pkg>/
  doc/
    overview.md     # the package's landing page
    conf.py         # Sphinx config for the standalone build only
  rosdoc2.yaml      # builder selection for docs.ros.org
```

These conventions matter:

- **The landing page is `overview.md`, not `index.md`.**
  `rosdoc2` generates its own `index` wrapper that links the auto-generated API.
  A file named `index.md` would shadow it, naming `overview.md` keeps the generated wrapper as the root.
- **`doc/conf.py` is for the standalone build only.**
  The combined site ignores it and uses the top-level `conf.py` instead (see staging below).

The top-level `nodl/doc/` tree is the combined site.
It holds the project-level pages (`index`, `concepts`, `schema`,`roadmap`), the generated schema reference, and the machinery that pulls the per-package trees in.

## Builds

### Standalone (docs.ros.org)

`rosdoc2 build` runs against one package's `doc/` + `rosdoc2.yaml`.
It reads `package.xml`, runs `sphinx-apidoc` (Python) and Doxygen/Breathe (C/C++) to generate the API reference, and seeds intersphinx from the package's dependencies.
Each package's `rosdoc2.yaml` selects the builders that fit its type: Python and C++ packages run apidoc/doxygen, CMake-macro-only packages (`ament_nodl`) skip both.

The resulting site is the artifact that will be produced in the ROS 2 buildfarm on the released packages.

CI for this build is in `.github/workflows/rosdoc2.yml`

### Combined (nodl.readthedocs.io)

The top-level `nodl/doc` Sphinx project builds every project-level page plus every package's `overview` in one site.
It does not re-author anything: at build time `nodl/doc/package_docs.py` copies each `<pkg>/doc/` tree into `nodl/doc/_generated/packages/<pkg>/` (gitignored), skipping the per-package `conf.py`.
`conf.py`'s `setup()` calls that staging step alongside the existing schema mirror, and `index.md` lists the staged `overview` pages in a "Packages" toctree.
Copying whole subtrees keeps each package's internal relative links valid inside the combined site.

CI for this build is in `.github/workflows/docs.yml`

## Adding a package to the docs

Four edits, all of which the combined build enforces under warnings-as-errors:

1. Add `<pkg>/doc/overview.md` and `<pkg>/doc/conf.py`.
2. Add `<pkg>/rosdoc2.yaml` with the builders for that package type.
3. Add the package to `PACKAGES` in `nodl/doc/package_docs.py` and to the "Packages" toctree in `nodl/doc/index.md`.
4. Add the package to the matrix in `.github/workflows/rosdoc2.yml`.

## Cross-references

Links have to resolve in both builds, so:

- **Package to top-level** (for example "see the concepts page") uses intersphinx against the `nodl` inventory:
  `` {external+nodl:doc}`concepts` ``.
  Each per-package `conf.py` registers that mapping, and `rosdoc2` also seeds it from `package.xml`, so the same link
  works standalone and combined.
- **Package to package** uses plain code-span mentions (`` `nodl_schema` ``), not `{doc}` links.
  An internal `{doc}` link would resolve in the combined one-site build but break standalone and on the buildfarm,
  where each package is a separate site.
  The combined site's nav lists every package for discovery.
- **Top-level to package** is a normal internal toctree/`:doc:` link, since the staged trees are part of the same
  project in the combined build.

## Scope notes

- The `nodl` metapackage `doc/` page contains the top-level site.
- `test_ament_nodl` is a test fixture and is not documented.
- Concept-level material (what NoDL is, the interface model, the schema field reference) lives only in `nodl/doc`.
  Package pages document their own surface and link up for shared concepts.
- Deep Python autodoc in the combined site is intentionally deferred: that venv does not install the packages, so API
  depth is left to the standalone `rosdoc2` build where the packages are importable.
