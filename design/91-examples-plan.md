# 91: First NoDL tutorials and demo-flow prototype

Status: Ready for implementation with current-capability limits.

# I. Specification

## 1. Objective

Add the first NoDL tutorials and test the proposed demo workflow against real ROS nodes.

This PR publishes:

- one tutorials overview;
- one basics tutorial;
- one `dummy_robot` tutorial.

The overview lists pendulum, ros2_control, and Nav2 as `TBD`. Separate PRs will add those tutorial files and implementations.

## 2. Scope

### In scope

- Add `tutorials/index.md`, `tutorials/basics.md`, and `tutorials/dummy-robot.md`.
- Add roadmap entries for the three deferred tutorials.
- Add implementation breadcrumbs for each deferred tutorial.
- Fetch a pinned `ros2/demos` checkout for live verification.
- Validate and register prototype NoDL documents.
- Run real C++ and Python basics nodes.
- Run the real `dummy_robot` bringup and headless system checks.
- Capture and inspect current raw Describe output.
- Document the intended future flow beside the verified current flow.
- Record product decisions and capability gaps found during rehearsal.

### Non-goals

- Do not add tutorial files or folders for pendulum, ros2_control, or Nav2.
- Do not implement missing NoDL core features in this PR.
- Do not emulate missing commands with tutorial-only compatibility code.
- Do not claim that current Describe output is a NoDL document.
- Do not claim forward generation, composition, semantic diff, or conformance works.
- Do not vendor the `ros2/demos` source tree.

## 3. Required outcomes

R1. The tutorials index must link to basics and `dummy_robot`.

R2. The tutorials index must list the three deferred tracks as `TBD`.

R3. Each deferred entry must record upstream target, purpose, prerequisites, and expected verification.

R4. Basics must cover conventional C++ and Python nodes.

R5. Basics must show the proposed Python composition flow as unavailable future behavior.

R6. `dummy_robot` must exercise the current Observe and manual-curation workflow.

R7. Every executable command marked as verified must run in automated verification.

R8. Every unavailable step must name its missing core capability.

R9. A clean workspace must reproduce the pinned `ros2/demos` verification environment.

R10. The PR must produce a short demo-flow findings report.

## 4. Acceptance tests

1. Build the documentation with warnings as errors.
2. Verify that only three tutorial Markdown files exist.
3. Validate all prototype NoDL documents.
4. Resolve all registered prototype documents from the ament index.
5. Launch the selected C++ and Python basics nodes.
6. Capture raw Describe output for both languages.
7. Launch `dummy_robot` without RViz and receive laser messages.
8. Verify the required robot transform separately from NoDL checks.
9. Capture raw Describe output for `dummy_laser`.
10. Recreate the environment from the locked manifest on a clean machine.

## 5. Readiness

The PR can implement and test the current workflow now.

The full target workflow remains blocked by Describe conversion, generation, composition, semantic diff, and conformance.

# II. Implementation

## 6. Proposed code tree

The tree is provisional. The initial implementation can adjust test filenames.

```text
nodl/
|-- nodl/doc/
|   |-- index.md
|   |   Adds the Tutorials navigation entry.
|   `-- tutorials/
|       |-- index.md
|       |   Overview, status table, roadmap, and follow-up breadcrumbs.
|       |-- basics.md
|       |   Current C++ and Python workflow plus target composition flow.
|       `-- dummy-robot.md
|           Current robot workflow plus target ROSCon flow.
|-- examples/
|   |-- README.md
|   |   Local setup, supported platform, and capability limitations.
|   |-- ros2_demos.lock.repos
|   |   Exact `ros2/demos` revision used by verification.
|   |-- bootstrap.bash
|   |   Creates a clean colcon workspace from the lockfile.
|   `-- nodl_tutorial_verification/
|       |-- package.xml
|       |   Test package dependencies and ownership.
|       |-- CMakeLists.txt
|       |   Registers prototype documents and installs test assets.
|       |-- nodl/
|       |   |-- cpp_talker.nodl.yaml
|       |   |   Curated C++ talker interface.
|       |   |-- py_talker.nodl.yaml
|       |   |   Curated Python talker interface.
|       |   |-- dummy_laser.nodl.yaml
|       |   |   Curated existing-node interface.
|       |   `-- robot_state_publisher.nodl.yaml
|       |       Separate existing-node TF endpoint interface.
|       |-- test/
|       |   |-- test_registration.py
|       |   |   Validation and ament index lookup.
|       |   |-- test_basics.py
|       |   |   C++ and Python startup and raw observation checks.
|       |   `-- test_dummy_robot.py
|       |       Laser, raw observation, and separate TF checks.
|       `-- expected/
|           |-- basics/
|           |   Stable application fields expected from raw observation.
|           `-- dummy_robot/
|               Stable application fields expected from raw observation.
|-- design/
|   `-- tutorial-demo-flow-findings.md
|       Decisions, friction, missing capabilities, and recommended CLI flow.
`-- .github/workflows/tutorial-examples.yml
    Imports pinned demos, builds the workspace, and runs current verification.
```

The prototype NoDL documents live in NoDL for this first pass. A later upstream PR may move them beside their node implementations.

## 7. First-PR boundary

### 7.1 Files created now

Create only these tutorial pages:

- `index.md`;
- `basics.md`;
- `dummy-robot.md`.

Do not create placeholder pages for the three deferred tutorials.

### 7.2 Roadmap entries

The overview contains this status table:

| Track | Status in this PR | Future implementation location |
|---|---|---|
| Basics | Prototype verified | `ros2/demos` basics packages |
| `dummy_robot` | Prototype verified | `ros2/demos/dummy_robot` |
| Pendulum | TBD | `ros2/demos/pendulum_control` |
| ros2_control | TBD | `ros-controls/ros2_control_demos` |
| Nav2 ControllerServer | Design preview | `ros-navigation/navigation2` |

Each `TBD` entry must include:

- the adoption question;
- the intended upstream package or class;
- the missing NoDL prerequisites;
- the expected live verification;
- the proposed follow-up PR boundary.

Add an HTML comment after each `TBD` entry. Use this shape:

```html
<!-- TODO(nodl-tutorials):
Target: <upstream package or class>
Prerequisites: <NoDL capabilities>
Proof: <required live tests>
PR boundary: <upstream and local artifacts>
-->
```

The comment is a maintainer breadcrumb. The visible roadmap text must still be understandable without the comment.

## 8. Current capabilities and verified flow

The first PR must use only behavior present at NoDL commit `427369df8af2e172797e088f7ec6d2bbe812b277`.

### 8.1 Available now

- `ros2 nodl validate` validates YAML and JSON NoDL documents.
- `ament_nodl_register_node` validates and registers documents during a build.
- `nodl_observe` observes a live ROS node into `rosgraph_msgs/Node`.
- `ros2 nodl describe` renders that raw observed message.
- Existing MCAP fixtures prove deterministic observation across supported RMW implementations.

### 8.2 Not available now

- Describe does not convert the raw message into NoDL.
- The schema does not accept fragments or a node base.
- No production composition resolver exists.
- No C++ or Python forward generator exists.
- No production semantic diff exists.
- No expected-versus-observed conformance command exists.

### 8.3 Verified current flow

The executable first-pass flow is:

1. Start an existing node.
2. Run `ros2 nodl describe` and save raw observation output.
3. Inspect the stable application interface fields.
4. Author or curate a NoDL document manually.
5. Run `ros2 nodl validate` on the curated document.
6. Register the curated document through `ament_nodl`.
7. Run the node and its existing behavior checks.
8. Record the gap between this flow and the desired flow.

The tests must not call this raw comparison semantic conformance.

### 8.4 Target future flow

The tutorials may show this intended flow as a design preview:

1. Describe a live node into a valid NoDL draft.
2. Curate author-only metadata and policy.
3. Compose reusable fragments.
4. Generate or bind a NoDL-forward implementation.
5. Observe the running implementation.
6. Compare expected and observed interfaces semantically.
7. Show a deliberate regression and semantic diff.

Every preview block must say that the commands are not yet implemented.

## 9. Basics tutorial

### 9.1 Current verified content

Use the existing `demo_nodes_cpp` and `demo_nodes_py` talker examples.

The live recipe must:

1. Launch each talker separately.
2. Confirm that each publishes the expected message type.
3. Capture raw Describe output for each node.
4. Validate separate curated NoDL documents.
5. Register and resolve both documents.
6. Compare stable application fields in the raw observations.

The comparison proves observation parity. It does not prove semantic NoDL conformance.

### 9.2 Python composition preview

Explain the desired composition of:

- a reusable `rclpy` node-base fragment;
- an application publisher fragment;
- explicit QoS;
- optional parameter or diagnostics capability fragments.

Do not add an invalid fragment document to registered fixtures. The current schema intentionally rejects fragments.

Use a clearly labelled non-executable schema sketch if the tutorial needs syntax discussion.

The findings report must record whether this composition model feels natural for Python users.

### 9.3 Deferred basics depth

Do not add services, actions, constrained parameters, or generated implementations in this first PR.

List those slices in the basics page as next steps after the prototype flow is accepted.

## 10. `dummy_robot` tutorial

### 10.1 Current verified content

Use the real `dummy_robot_bringup` and `dummy_laser` executable.

The automated recipe must:

1. Launch the robot without RViz.
2. Confirm that `dummy_laser` publishes `sensor_msgs/msg/LaserScan` on `scan`.
3. Capture raw Describe output for `dummy_laser`.
4. Validate and register the curated `dummy_laser` document.
5. Verify that the required transform for `single_rrbot_hokuyo_link` is available.
6. Keep the `robot_state_publisher` document separate.
7. Shut down every launched process cleanly.

The TF assertion is a robot-system test. It is not NoDL endpoint conformance.

### 10.2 Manual visual check

Document the existing RViz launch and expected robot and laser result.

The visual check is optional in CI and required for the internal demo rehearsal.

### 10.3 Target ROSCon preview

Show the intended observe, curate, generate, compose, conform, regress, restore, and RViz sequence.

Mark generation, composition, semantic diff, and conformance steps as unavailable.

The findings report must decide whether `dummy_laser` remains the best hero-node entry point.

## 11. Raw observation test policy

Do not store complete raw observations as cross-version YAML goldens.

Full observations contain framework and middleware details that can vary across ROS distributions and RMW implementations.

Assert only stable application fields for tutorial verification:

- node name;
- application topic name;
- endpoint direction;
- ROS interface type;
- required QoS fields when the RMW reports them;
- selected parameter names where applicable.

Reuse `nodl_observe` MCAP fixtures for observation-backend regression coverage. Do not duplicate those fixtures under `examples/`.

If an RMW reports a known unknown value, the tutorial test must record it as unverified. It must not fabricate a value.

## 12. Live workspace and CI

### 12.1 Lockfile

Pin the reviewed `ros2/demos` revision in `ros2_demos.lock.repos`.

Record the selected ROS distribution, Ubuntu version, RMW, NoDL commit, and demos commit in `examples/README.md`.

The initial platform should match the available upstream branch and NoDL core build support.

### 12.2 Bootstrap

The bootstrap script must reject a non-empty destination.

The script imports `ros2/demos`, installs declared dependencies, builds the selected packages, and records resolved revisions.

The script must not edit either source checkout.

### 12.3 CI

The workflow runs when tutorial, example, or workflow files change.

CI must:

1. Import the locked upstream revision.
2. Build NoDL and the tutorial verification package.
3. Build the selected `ros2/demos` packages.
4. Run registration, basics, and `dummy_robot` tests.
5. Build documentation with warnings as errors.
6. Upload logs and resolved revisions on failure.

Do not add a moving-branch canary in this first PR. Add it after the locked prototype is stable.

## 13. Demo-flow findings report

The PR must add a short internal findings document under `design/`.

The report must answer:

- Is raw Describe output useful for manual curation?
- Which infrastructure endpoints should default Describe hide?
- Can one logical NoDL shape explain both C++ and Python basics?
- Does the proposed Python fragment model feel natural?
- Is manual document registration understandable?
- Which command boundaries create the most demo friction?
- Is `dummy_laser` the correct hero-node entry point?
- Which missing capability must land next?

Use evidence from the executable recipes. Do not fill the report with speculative answers before rehearsal.

## 14. Detailed test matrix

| Requirement | Automated evidence | Manual evidence |
|---|---|---|
| R1-R3 | Sphinx build, link check, roadmap content test | Documentation review |
| R4-R5 | C++ and Python startup and raw observation checks | Composition UX review |
| R6-R8 | Dummy robot launch, validation, registration, and gap labels | Target-flow rehearsal |
| R9 | Clean locked-workspace build | Optional second machine |
| R10 | Findings file existence and required-question check | Completed findings review |

Missing upstream sources, prototype documents, or expected field assertions must fail.

Tests must not skip because a missing capability is unavailable. Unavailable capabilities are excluded and documented.

## 15. Implementation phases

### Phase 0 — workspace proof

- Outcome: Reproduce a pinned NoDL and `ros2/demos` workspace.
- Affected paths: lockfile, bootstrap script, examples README.
- Tasks: Pin revisions, import sources, install dependencies, and build selected packages.
- Tests: Clean-workspace success and non-empty-destination rejection.
- Gate: Two clean workspace builds resolve the same commits.

### Phase 1 — prototype documents and registration

- Outcome: Validate and register the first curated documents.
- Affected paths: verification package, NoDL fixtures, registration tests.
- Tasks: Add C++ talker, Python talker, `dummy_laser`, and `robot_state_publisher` documents.
- Tests: Schema validation, build-time validation, ament lookup, and byte equality.
- Gate: All four documents validate and resolve from the installed workspace.

### Phase 2 — live current-flow verification

- Outcome: Prove the executable part of the current tutorial flow.
- Affected paths: basics and dummy robot tests, stable expected fields.
- Tasks: Launch real nodes, capture raw observations, assert stable fields, test laser and TF, and clean up.
- Tests: Both basics languages and headless `dummy_robot` pass from the locked workspace.
- Gate: No test uses a fake core command or duplicated observation backend.

### Phase 3 — tutorials and roadmap

- Outcome: Publish two tutorials and three actionable roadmap entries.
- Affected paths: tutorials index, basics, `dummy_robot`, top-level navigation.
- Tasks: Separate verified commands from target-flow previews and add TODO breadcrumbs.
- Tests: Sphinx warnings-as-errors, links, tutorial file count, and verified-command audit.
- Gate: Only three tutorial files exist and every verified command has automated evidence.

### Phase 4 — internal rehearsal and findings

- Outcome: Decide whether the proposed demo flow is suitable.
- Affected paths: findings report and tutorial corrections.
- Tasks: Run both recipes, perform the RViz check, answer findings questions, and revise confusing steps.
- Tests: Repeat the locked current flow after documentation corrections.
- Gate: The report recommends the next core capability and confirms or changes the hero-node choice.

### Phase 5 — CI integration

- Outcome: Keep the first-pass workflow reproducible.
- Affected paths: tutorial examples workflow.
- Tasks: Add locked build, tests, docs, logs, and revision artifacts.
- Tests: Required job success plus one controlled fixture-failure check.
- Gate: CI fails on a changed expected application field and passes after restoration.

## 16. Follow-up PR breadcrumbs

### Pendulum

- Target: `ros2/demos/pendulum_control`.
- Purpose: Existing C++ migration with real-time-sensitive behavior.
- Prerequisites: Advanced C++ bindings and logical-node registration.
- Proof: Preserve existing behavior, allocator, memory strategy, QoS, executor, and scheduling configuration.

### ros2_control

- Target: Examples 1 and 17 in `ros2_control_demos`.
- Purpose: Framework capability composition and expected-versus-observed drift.
- Prerequisites: Fragment composition, logical-node registration, semantic diff, and conformance.
- Proof: Detect missing diagnostics, hardware status, and the separate custom-node status.

### Nav2

- Target: C++ `ControllerServer` plus Python `BasicNavigator`.
- Purpose: Provider-base and client-capability composition across C++ and Python.
- Prerequisites: Composition, semantic diff, conformance, and stable logical-node ownership.
- Proof: Verify C++ lifecycle, bond, TF, and application interfaces plus Python client capabilities.

## 17. Stop conditions

Stop if the PR starts implementing schema, conversion, composition, generation, diff, or conformance logic.

Stop if a tutorial labels raw field assertions as semantic conformance.

Stop if a preview command appears executable without a capability-warning label.

Stop if deferred tutorial files or folders are added.

Stop if tests copy the `nodl_observe` backend or its MCAP corpus.

Stop if the TF transform assertion is described as endpoint conformance.

Stop if the live workspace modifies the fetched upstream checkout.

## 18. Definition of done

- The documentation contains only the overview, basics, and `dummy_robot` tutorial files.
- The overview lists pendulum, ros2_control, and Nav2 as `TBD` with breadcrumbs.
- Prototype NoDL documents validate and resolve from the ament index.
- Real C++ and Python basics nodes produce the asserted raw application fields.
- The real `dummy_robot` system produces laser data and the required transform.
- Verified current commands and unavailable target commands are visually distinct.
- The locked workspace reproduces the tests from a clean machine.
- CI builds documentation and runs the current-capability verification.
- The findings report identifies the next capability and records the hero-node decision.
- No missing core feature is implemented or emulated inside the tutorial harness.

## 19. Final audit

1. Confirm that only three tutorial Markdown files exist.
2. Run the clean locked-workspace bootstrap twice.
3. Validate and resolve every prototype document.
4. Run C++ and Python basics verification.
5. Run headless `dummy_robot` verification.
6. Perform the manual RViz check.
7. Build documentation with warnings as errors.
8. Verify all preview blocks have unavailable-capability labels.
9. Verify all deferred entries contain visible context and HTML breadcrumbs.
10. Review the findings report and create the recommended core follow-up issue.
