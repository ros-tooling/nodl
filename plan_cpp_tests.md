# Integration test plan for `nodl_generator_cpp`

## Goal

Prove the full loop: **NoDL YAML → generated C++ base class → user-written derived class → built and exercised in a ROS 2 environment.** The existing `nodl_generator_cpp/test/test_generator.py` covers Python-side logic and template rendering; this plan covers what only a real `colcon` + `rclcpp` build can catch.

## Package layout

One package — `test_nodl_generator_cpp` — grown into a matrix of feature-axis fixtures. Don't fan out into multiple packages: per-package overhead is real, and there's nothing per-axis that needs its own `package.xml`.

```
test_nodl_generator_cpp/
  CMakeLists.txt
  package.xml
  fixtures/
    pubsub_node.nodl.yaml          # axis 1 — START HERE
    service_node.nodl.yaml         # axis 2 — later
    action_node.nodl.yaml          # axis 3 — later
    qos_node.nodl.yaml             # axis 4 — later
    params_node.nodl.yaml          # axis 5 — later
    pubsub_lifecycle_node.nodl.yaml  # axis 6 — later (lifecycle = flag, not standalone axis)
  derived/                         # the "user code" — handwritten subclasses
    pubsub_node.hpp / .cpp
    service_node.hpp / .cpp
    ...
  test/
    test_pubsub.cpp
    test_service.cpp
    ...
```

Three-layer separation per axis is deliberate:
- **Generated base** (`pubsub_node` library, emitted by `nodl_generate_cpp()`) — the contract.
- **Derived class** (`pubsub_node_derived` library) — what a real user would write. Override callbacks, publish through generated handles.
- **gtest** (`test_pubsub`) — spins an executor, asserts behavior.

When something breaks, the failure mode points at exactly one layer.

## CMake pattern (repeated per axis)

```cmake
nodl_generate_cpp(pubsub_node fixtures/pubsub_node.nodl.yaml)

add_library(pubsub_node_derived derived/pubsub_node.cpp)
target_link_libraries(pubsub_node_derived PUBLIC pubsub_node)

ament_add_gtest(test_pubsub test/test_pubsub.cpp)
target_link_libraries(test_pubsub pubsub_node_derived)
```

## Axes and what each test must prove

| Axis | What only this layer can catch | What to assert |
|---|---|---|
| **pubsub** | Wrong topic baked in, wrong type, callback signature mismatch, missing `create_publisher` in ctor | Real round-trip: test-side publisher sends on `/in`, derived re-publishes on `/out`, test-side subscriber receives. |
| **service** | Wrong service name, server/client mixup, request/response type mixup | Test-side client calls derived's server, asserts response. Derived's client calls test-side server, asserts response received. |
| **action** | Wrong action name, goal/result/feedback wiring | Test-side client sends goal, drains feedback, asserts result. |
| **qos** | Wrong `.reliable()`/`.best_effort()` branch, off-by-one depth, wrong durability | `publisher->get_actual_qos()` matches declared. **Do not** test behavioral QoS semantics (transient_local replay, deadline callbacks) — too flaky, and the QoS object itself is the contract. |
| **params** | `ParamListener` not wired, defaults lost in YAML hop, `read_only` not propagated, `params_` inaccessible from derived | `params_.foo == default`, `has_parameter("foo")`, `describe_parameter("foo").read_only` flag. **Do not** retest `generate_parameter_library` itself (dynamic updates, validators) — that's gpl's job. |
| **lifecycle** | Not a 5th axis — it's a `base: lifecycle_node` variant of any other axis | Drive state machine (`configure` → `activate`), re-assert the underlying axis still works in active state. |

## Scope discipline

Two failure modes to guard against, both about overgrowing this matrix:

1. **Don't smuggle multiple axes into one fixture.** The pubsub fixture uses a boring QoS (`KEEP_LAST/10/RELIABLE`) and no parameters. A red `test_pubsub` should mean exactly one thing.
2. **Don't add an axis without a generator-specific failure mode in mind.** If you can't name what *the generator* could plausibly get wrong that the new test would catch, the assertion belongs inside an existing test, not as a new fixture.

## CI environment

This layer needs a real ROS 2 install: `colcon`, `rclcpp`, `std_msgs`, `lifecycle_msgs`, `example_interfaces`, `generate_parameter_library`. MacOS CI was recently removed from this repo (commit `4ee02db`); plan to run this suite in Linux/container CI only. The Python-side pytest layer stays as the cross-platform fast loop.

## Rollout order

1. **Now:** Convert existing `test_node.nodl.yaml` + `test_generated_node.cpp` into the new layout with just the pub/sub axis. Make the gtest do a real round-trip, not just compile-and-handle-exists checks.
2. **+ params axis:** Move the parameter assertions out of the pubsub test into their own fixture/test.
3. **+ qos axis:** Multi-publisher fixture, `get_actual_qos()` assertions.
4. **+ services axis.**
5. **+ actions axis.**
6. **+ lifecycle variants** of axes 1–5 where they meaningfully exercise different generator codepaths.

Each step is additive — no rework of prior steps.

## Open questions

- **Generator API ergonomics.** Writing the derived class is itself a UX review of the emitted API. If the override signatures or member access patterns feel awkward, fix them before three more axes calcify around them.
- **`description:` fields and namespace handling.** Worth an assertion inside existing tests rather than their own axes — flag if a generator bug surfaces.
