# Tutorial demo-flow findings

Status: Rehearsal pending

Review baseline: NoDL `427369df8af2e172797e088f7ec6d2bbe812b277`, `ros2/demos`
`f8d20abaec2be76c7062b2a0242ae6f82e2857b8`.

This document records evidence from the basics and `dummy_robot` tutorial rehearsal. Do not fill an answer from the
target design alone.

## Confirmed before rehearsal

- Validate and ament registration accept the curated tutorial documents.
- Observe records live nodes as `rosgraph_msgs/Node`.
- Current `ros2 nodl describe` renders that raw message instead of a NoDL document.
- Current NoDL v2 rejects fragment and node-base fields.
- Generation, semantic diff, and conformance are not present on `main`.

## Questions for the WG meeting

### Is raw Describe output useful for manual curation?

Finding: TBD after live rehearsal.

### Which infrastructure endpoints should default Describe hide?

Finding: TBD after comparing the two talkers and `dummy_laser`.

### Can one logical NoDL shape explain C++ and Python basics?

Finding: TBD. The first documents differ only in publisher depth.

### Does the proposed Python fragment model feel natural?

Finding: TBD. The current schema sketch is intentionally non-executable.

### Is registration understandable for an example author?

Finding: TBD after building `nodl_tutorial_verification` from a clean workspace.

### Which missing command creates the most demo friction?

Finding: TBD. Candidates are Describe conversion, composition, generation, semantic diff, and conformance.

### Is `dummy_laser` the correct hero-node entry point?

Finding: TBD after the headless and RViz rehearsals.

### Which capability should land next?

Recommendation: TBD after rehearsal.

## Rehearsal record

| Check | Result | Evidence or issue |
|---|---|---|
| Clean locked workspace | Pending | |
| C++ talker observation | Pending | |
| Python talker observation | Pending | |
| Curated document validation | Pending | |
| Ament registration | Pending | |
| Headless dummy robot | Pending | |
| Laser frame TF lookup | Pending | |
| RViz visual result | Pending | |
