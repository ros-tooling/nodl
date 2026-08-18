# nodl_generator_cpp

`nodl_generator_cpp` generates a C++ abstract base class from a NoDL document.
The generated class inherits from the appropriate node type (determined by includes), creates all endpoint handles
in its constructor, and exposes pure-virtual callbacks for inbound endpoints.
You subclass it and write only business logic.

Generated files are never edited by hand — they are regenerated whenever the `.nodl.yaml` changes.
This is the same generate-always pattern used by `rosidl_generator_cpp` and `generate_parameter_library`.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.
This package implements the "forward" workflow: a NoDL document is the source of truth that makes a node's interface
exist.

## Usage

```bash
python -m nodl_generator_cpp \
  --nodl-file my_node.nodl.yaml \
  --output-dir generated/ \
  --target-name my_node
```

| Flag | Required | Description |
|---|---|---|
| `--nodl-file` | Yes | Path to the NoDL document. |
| `--output-dir` | Yes | Directory to write generated files into (created if absent). |
| `--target-name` | Yes | Used as the node name and the stem of all generated filenames. Must be a valid C++ identifier. |

## Generated files

The generator produces up to four files, depending on the document's contents:

| File | Always | Contents |
|---|---|---|
| `<target>.hpp` | Yes | Abstract base class header. |
| `<target>.cpp` | Yes | Constructor implementation — creates all handles. |
| `<target>_parameters.yaml` | If parameters | `generate_parameter_library` YAML, converted from NoDL parameters. |
| `<target>_parameters.hpp` | If parameters | `generate_parameter_library` C++ header, generated from the YAML above. |

## Example

Given this NoDL input:

```yaml
nodl_version: 2

include:
  - ref: nodl://rclcpp/node

publishers:
  - name: status
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE

subscriptions:
  - name: cmd_vel
    type: geometry_msgs/msg/Twist
    qos:
      history: KEEP_LAST
      depth: 1
      reliability: BEST_EFFORT
```

The generator produces this header:

```cpp
// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <geometry_msgs/msg/twist.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

class MyNodeBase : public rclcpp::Node
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Publishers ---
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_status_;

  // --- Subscription callbacks ---
  virtual void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr msg) = 0;

private:

  // --- Subscriptions ---
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr sub_cmd_vel_;
};
```

And this source file:

```cpp
// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
{

  // Create publishers
  pub_status_ = this->create_publisher<std_msgs::msg::String>("status", rclcpp::QoS(10).reliable());

  // Create subscriptions
  sub_cmd_vel_ = this->create_subscription<geometry_msgs::msg::Twist>(
    "cmd_vel",
    rclcpp::QoS(1).best_effort(),
    [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
      this->on_cmd_vel(msg);
    });
}
```

The user subclasses `MyNodeBase` and implements `on_cmd_vel()`.

## Generated class layout

The generated class uses visibility to separate concerns:

| Visibility | What | Naming | Why |
|---|---|---|---|
| **Protected** | Publishers | `pub_<name>_` | Subclass needs `publish()`. |
| **Protected** | Service clients | `cli_<name>_` | Subclass needs `async_send_request()`. |
| **Protected** | Action clients | `action_cli_<name>_` | Subclass needs `async_send_goal()`. |
| **Protected** | Parameter listener & params | `param_listener_`, `params_` | Subclass reads parameters. |
| **Protected, pure-virtual** | Subscription callbacks | `on_<name>(msg)` | Subclass implements business logic. |
| **Protected, pure-virtual** | Service server callbacks | `on_<name>(request, response)` | Subclass implements business logic. |
| **Protected, pure-virtual** | Action server callbacks | `on_<name>_goal()`, `on_<name>_cancel()`, `on_<name>_accepted()` | Subclass implements business logic. |
| **Private** | Subscription handles | `sub_<name>_` | Wiring only — subclass has no reason to touch these. |
| **Private** | Service server handles | `srv_<name>_` | Wiring only. |
| **Private** | Action server handles | `action_srv_<name>_` | Wiring only. |

Entity names are sanitised for use as C++ identifiers: leading `~/` or `/` is stripped, remaining `/` becomes `_`.

## Base class and provenance

The generator does not hardcode what class to inherit from.
Instead, it walks the NoDL document's include tree to determine the base class and to filter out entities that are
already provided by an existing implementation.

### The `codegen.cpp` metadata

A NoDL document can carry a `codegen.cpp` field declaring that it has an existing C++ implementation.
The schema for this field is defined in {repo}`nodl_generator_cpp/nodl_generator_cpp/schemas/codegen_cpp.schema.yaml`
and validated by `nodl_generator_cpp`, not `nodl_schema`.

For example, `nodl://rclcpp/node` declares itself as a base-class provider:

```yaml
# nodl://rclcpp/node
nodl_version: 2
codegen:
  cpp:
    role: BASE_CLASS
    class: rclcpp::Node
    header: rclcpp/rclcpp.hpp

publishers:
  - name: /rosout
    type: rcl_interfaces/msg/Log
    qos: {history: KEEP_LAST, depth: 1, reliability: RELIABLE}
# ... /parameter_events, parameter services, use_sim_time, etc.
```

A consumer simply includes it — no codegen metadata of its own is needed:

```yaml
# my_node.nodl.yaml
nodl_version: 2
include:
  - ref: nodl://rclcpp/node
publishers:
  - name: /status
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}
```

### Barriers and entity filtering

An included document that carries `codegen.cpp` is an **implementation barrier**.
All entities it declares — and all entities in documents *it* transitively includes — are *provided*: the existing
implementation already handles them, so the generator filters them out.

```
root (being generated — no codegen)
 ├── include: nodl://rclcpp/node          [has codegen → barrier]
 │    → /rosout, /parameter_events, …      filtered out
 └── own: /status                          scaffolded
```

The generator builds a provenance map: each entity maps to the `codegen.cpp` of its provider, or is absent (meaning
the generator must scaffold it).

### Inheritance chains

A base-class provider can itself include another base class.
`rclcpp_lifecycle::LifecycleNode` extends `rclcpp::Node`:

```
root (being generated)
 └── include: nodl://rclcpp_lifecycle/lifecycle_node   [codegen: BASE_CLASS → barrier]
      └── include: nodl://rclcpp/node                  [codegen: BASE_CLASS, behind barrier]
           → /rosout, /parameter_events, …              all attributed to lifecycle_node
```

The inner `rclcpp::Node` sits behind `LifecycleNode`'s barrier, so all of Node's entities are attributed to
LifecycleNode.
The generator sees exactly one base class — the outermost barrier — and inherits from it.

### Error: multiple direct base classes

If the root document directly includes two unrelated base-class providers, the generator rejects the input — C++
single-inheritance means it cannot produce a class that inherits from two unrelated node types:

```
root
 ├── include: nodl://rclcpp/node                      [codegen: BASE_CLASS]
 └── include: nodl://rclcpp_lifecycle/lifecycle_node   [codegen: BASE_CLASS]
```

These are siblings; neither is behind the other's barrier.

### No base class

A document that does not include any `codegen.cpp.role: BASE_CLASS` provider is also an error.
Every generated node must inherit from a concrete base.

## Parameters

NoDL parameters are compatible with [`generate_parameter_library`](https://github.com/PickNikRobotics/generate_parameter_library)
by design — the NoDL parameter schema is a formalization of genparamlib's implicit schema.

The generator converts NoDL parameters to a genparamlib YAML file, then delegates to genparamlib to produce the
C++ parameter header.
No `declare_parameter()` calls appear in the generated templates.

The generated base class holds two protected members for parameter access:

```cpp
protected:
  my_node::ParamListener param_listener_;
  my_node::Params params_;
```

Parameters declared by included documents behind a barrier (e.g. `use_sim_time` from `rclcpp::Node`) are filtered
out and do not appear in the genparamlib YAML or the generated header.

## Relationship to other packages

The NoDL document consumed by this generator is validated by `nodl_schema`.
Include resolution and the document tree are provided by `nodl_schema`'s loader.
The `codegen.cpp` sub-object is opaque to `nodl_schema` — its schema and interpretation are owned entirely by this
package.
For registering a NoDL document with the ament index, see the `ament_nodl` package.
