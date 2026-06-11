# Per-package documentation: proposal for review

Status: accepted and implemented (Option C, intersphinx from the outset).
The `nodl` metapackage stays documented by the top-level site with no page of its own; `test_ament_nodl` is excluded.
Scope: how to author, preview, and host per-package docs alongside the existing top-level `nodl.readthedocs.io` site,
in a way that ports cleanly to `rosdoc2` / `docs.ros.org` later.

## Current state

- One Sphinx project lives at `nodl/doc/` and is the only documented surface.
  It builds the project-level pages (`index`, `concepts`, `schema`, `roadmap`) plus a generated schema reference.
- One Read the Docs project builds `nodl/doc/conf.py` (see `.readthedocs.yaml`), and CI mirrors that build with
  warnings-as-errors via `poe build` (`.github/workflows/docs.yml`).
- The four shipped packages (`nodl_schema`, `ros2nodl`, `ament_nodl`, `nodl`) have no docs of their own.
  `test_ament_nodl` is a test fixture and needs no public docs.
- `index.md` already lists the packages textually with a placeholder:
  "Per-package documentation will land here as each package's surface stabilizes."

## What rosdoc2 expects (grounded in this workspace)

Other packages in this workspace already use rosdoc2, so we can match a known-good shape:

- `rosgraph_monitor/rosdoc2.yaml` + `rosgraph_monitor/doc/{conf.py,index.rst,...}`: a per-package `doc/` tree with its
  own minimal `conf.py`, a `rosdoc2.yaml` selecting doxygen + sphinx builders, and `generate_package_index: true`.
- `generate_parameter_library/rosdoc2.yaml`: a near-empty config (`builders: [sphinx: {}]`) that lets rosdoc2 supply
  defaults.

Key rosdoc2 properties relevant to us:

- rosdoc2 builds each package **independently** and emits one site per package
  (on the buildfarm: `docs.ros.org/en/<distro>/p/<package>/`).
- It pulls in the package's `README`, runs `sphinx-apidoc` for Python and Doxygen/Breathe for C/C++ automatically.
- It wires **intersphinx** mappings to depended-upon packages from `package.xml`, so cross-package references are
  symbolic, not path-based.
- On `docs.ros.org` there is no single combined site we control; the buildfarm aggregates per-package sites.
  Any "one site" we want before that is our own responsibility.

The takeaway: the durable, must-have artifact is a **per-package `doc/` tree plus `rosdoc2.yaml` for every package**.
A combined site is a convenience we layer on top for the pre-release period.

## The core decision

The prompt asks whether subpackage docs are separate RTD projects or folded into the single RTD site.
Three architectures, with tradeoffs:

### Option A: keep one site, author package sections inside `nodl/doc/`

Package docs become pages under `nodl/doc/packages/<pkg>.md`, all in the existing source tree.

- Pros: trivial cross-references (all internal), one PR preview, no new machinery.
- Cons: docs live away from each package's source; nothing is rosdoc2-shaped, so docs.ros.org is a second, separate
  effort later; does not satisfy "rosdoc2-ish docs for every package."

### Option B: one independent Sphinx project per package, multiple RTD (sub)projects

Each package gets `doc/` + `conf.py` + `rosdoc2.yaml`; RTD subprojects host them under
`nodl.readthedocs.io/projects/<pkg>/`; cross-references go through intersphinx.

- Pros: 1:1 with the docs.ros.org model; each preview is exactly what ships.
- Cons: multiple RTD projects to provision and keep green, multiple PR-preview builds, intersphinx wiring needed now,
  and the "single official site" degrades to a hub of links. Heaviest option.

### Option C (recommended): per-package `doc/` authored in each package, aggregated into one RTD build

- Every package gets a real, standalone-buildable `doc/` tree and a `rosdoc2.yaml` (the durable rosdoc2 artifact).
- The existing top-level `nodl/doc` build **stages** those per-package trees into the single Sphinx source at build
  time and lists them in a "Packages" toctree section.
- One RTD project, one PR preview, one official site for the pre-release period; later, rosdoc2 builds each package's
  `doc/` directly with no re-authoring.

Why C: it gives both deliverables from a single authoring location, keeps docs next to their package source, and reuses
a pattern already present in this repo (`conf.py`'s `setup()` already calls `schema_reference.mirror_schemas_for_docs()`
to stage generated content into `nodl/doc/_generated/`). Staging package docs is the same move.

## How Option C works concretely

### Layout

```
nodl_schema/
  doc/
    index.md            # package overview, concepts-level + API entry
    rosdoc2.yaml        # standalone build config for docs.ros.org
ros2nodl/
  doc/
    index.md
    rosdoc2.yaml
ament_nodl/
  doc/
    index.md
    rosdoc2.yaml
nodl/
  doc/                  # unchanged top-level site
    conf.py             # setup() also stages sibling package docs
    index.md            # "Packages" toctree points at staged trees
    _generated/
      packages/<pkg>/   # gitignored, populated at build time
```

### Aggregation mechanism

Extend `conf.py`'s existing `setup(app)` with a `mirror_package_docs()` step that copies each
`../../<pkg>/doc/` tree into `nodl/doc/_generated/packages/<pkg>/` (already gitignored via `/_generated/`).
The top-level `index.md` toctree then references `_generated/packages/<pkg>/index`.
Copying whole subtrees keeps each package's internal relative links valid inside the combined build.
No symlinks are committed, and nothing about the per-package sources assumes the combined build.

### Cross-reference strategy (the one real subtlety)

Links must resolve both in the combined build and in standalone rosdoc2 builds. Recommended rule:

- Package-to-top-level references (for example, "see the schema reference") use **intersphinx** against an inventory
  named for the top-level `nodl` docs. rosdoc2 generates this mapping from `package.xml` dependencies for the
  standalone build; the combined `conf.py` registers the same mapping name pointing at the local/published top-level
  build. One link style works in both contexts.
- Top-level-to-package references are plain internal toctree/`:doc:` links in the combined build, since the staged
  trees are part of the same Sphinx project.
- Simpler fallback if intersphinx wiring is deferred: package docs link "up" using absolute in-project doc refs
  (`` {doc}`/concepts` ``), which resolve from any staged location in the combined build, and degrade to an
  intersphinx ref only when built standalone. We can start with the fallback and add intersphinx when the first
  package goes to docs.ros.org.

### Avoiding repetition

- Concept-level material (what NoDL is, the interface model, the schema reference) stays **only** in `nodl/doc`.
- Each package page documents that package's specifics and links up for shared concepts:
  - `nodl_schema`: the Python API (`load_nodl`, `dump_nodl`, `load_schema`, `validate`), the typed models, and how to
    validate documents programmatically. Schema field reference stays top-level; the package page links to it.
  - `ros2nodl`: the `ros2 nodl <verb>` CLI surface (currently `validate`), usage examples, exit codes.
  - `ament_nodl`: the `ament_nodl_register_node` CMake macro and ament-index registration, for package authors.
  - `nodl`: the metapackage; mostly a pointer to the others and to the top-level site, minimal standalone content.

## Implementation plan (after acceptance)

1. Add `doc/index.md` + `rosdoc2.yaml` to `nodl_schema` first as the pilot (richest surface, Python apidoc exercises
   the most rosdoc2 behavior). Author it standalone-buildable.
2. Add `mirror_package_docs()` to `nodl/doc/conf.py` `setup()` and a "Packages" toctree section in `index.md`;
   confirm the combined RTD/CI build (`poe build`, warnings-as-errors) stays green and the PR preview shows the page.
3. Decide and apply the cross-reference rule (start with the `/abs-doc-ref` fallback unless we want intersphinx now).
4. Repeat for `ros2nodl`, `ament_nodl`, and the `nodl` metapackage.
5. Validate a standalone `rosdoc2` build of `nodl_schema` locally to confirm the same sources build both ways before
   we commit to the pattern for all packages.

## Decisions (resolved at review)

1. Option C: per-package `doc/` trees aggregated into the single RTD site.
2. Intersphinx from the outset. Per-package docs reference the top-level site through the `nodl` inventory; the doc
   target names carry no leading slash (for example `` {external+nodl:doc}`concepts` ``), matching the published
   inventory.
3. The `nodl` metapackage stays documented by the top-level site; it gets no `doc/` page.
4. `test_ament_nodl` is excluded.

## What was implemented

- `nodl/doc/package_docs.py`: stages each package's `doc/` tree into `_generated/packages/<pkg>/` at build time,
  called from `conf.py`'s `setup()` alongside the existing schema mirror.
- `conf.py`: added `sphinx.ext.intersphinx` plus the `nodl` mapping; `index.md` gained a "Packages" toctree.
- `nodl_schema`, `ros2nodl`, `ament_nodl`: each got `doc/index.md`, a standalone `doc/conf.py` (myst + intersphinx),
  and a `rosdoc2.yaml`. The CMake-only `ament_nodl` config skips apidoc/doxygen.
- `.pre-commit-config.yaml`: excluded `rosdoc2.yaml` from `polymath-yaml`, since rosdoc2's mandated two-document
  layout is rejected by yamlfix.

The combined build is green under warnings-as-errors (`poe build`), and all pre-commit hooks pass.

## Remaining (deferred) work

- Step 5 from the plan: validate a standalone `rosdoc2` build of each package locally / on the buildfarm. The combined
  build is the only path exercised so far. Notably, cross-*package* links (for example `ros2nodl` to `nodl_schema`) use
  internal relative `{doc}` refs that resolve in the combined site but will need intersphinx wiring (from `package.xml`
  dependencies) to resolve in standalone builds.
- Deep autodoc of the Python API in the combined site is intentionally not done: the docs venv does not install the
  packages, so API pages are curated prose with `{repo}` source links. The standalone rosdoc2 build is where
  `sphinx-apidoc` runs.
