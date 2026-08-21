# Why NoDL?

ROS 2 applications spend too much time on interface plumbing: creating endpoints, tracking QoS and parameters,
keeping launch configuration aligned with code, and debugging wiring that is only visible at runtime. Those interfaces
are usually undocumented by default.

NoDL makes the ROS interface an explicit, reviewed contract. It does not replace application behavior: a controller's
algorithm, a robot's timing, and a navigator's goal policy remain ordinary application code.

## One contract, multiple uses

Specify one NoDL contract for endpoints, types, QoS, parameters, and composed capabilities. Start from a new design
or recover a draft from an existing node with `describe`. Then use it to:

- **Generate implementation** — interface wiring; behavior stays handwritten.
- **Generate documentation** — an exact interface reference.
- **Conform** — detect drift in the observed running graph.

Adopt any use first; add the others later.

NoDL checks graph contracts. It does not prove behavioral success, TF frame semantics, scheduling, or real-time
guarantees.

## Start where it helps

NoDL supports gradual adoption without requiring a rewrite:

| Starting point | First value |
|---|---|
| Existing node | Describe and review its interface before changing implementation code |
| New node | Specify the interface once and generate its binding |
| Existing documentation or integration test | Generate a reference or make interface drift visible |
| Framework ecosystem | Compose reusable capabilities without hiding their provenance |
