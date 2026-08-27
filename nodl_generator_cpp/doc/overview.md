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

## CMake integration

The `nodl_generate_cpp()` CMake macro is the primary user-facing API.
Three lines in your `CMakeLists.txt` are the entire integration surface:

```cmake
find_package(nodl_generator_cpp REQUIRED)

nodl_generate_cpp(my_node_base nodl/my_node.nodl.yaml)

add_executable(my_node src/my_node.cpp)
target_link_libraries(my_node PRIVATE my_node_base)
```

### What the macro does

`nodl_generate_cpp(TARGET NODL_FILE)` creates a STATIC library target named `TARGET` that you link against.
It handles everything:

| Step | When | What happens |
|---|---|---|
| Dependency discovery | Configure time | Runs `--cmake-deps` to determine all NoDL source paths, ROS package dependencies, and the list of files the generator will produce. |
| `find_package` | Configure time | Automatically calls `find_package` for every ROS dependency (message, service, action, and base-class packages). |
| File watching | Configure time | Registers every file in the NoDL include tree as a `CMAKE_CONFIGURE_DEPENDS`, so any change to the root or a transitive include triggers a reconfigure. |
| Code generation | Build time | Runs the full generator via `add_custom_command`, only when an input file has changed. |
| Library creation | Build time | Compiles the generated `.cpp` into a STATIC library and sets up include directories. |
| ROS linking | Build time | Links all ROS dependencies via `${pkg}_TARGETS`. |
| Parameter library | Build time | When the document has parameters, links `generate_parameter_library` and its transitive dependencies (`fmt`, `rsl`, `tcb_span`, etc.). |

### Arguments

| Argument | Description |
|---|---|
| `TARGET` | Name of the library target to create. Also used as the C++ class stem (`<TARGET>Base`) and for all generated filenames. |
| `NODL_FILE` | Path to the `.nodl.yaml` file, relative to `CMAKE_CURRENT_SOURCE_DIR`. |

### Rebuild behavior

Every file in the NoDL include tree — the root document and all transitive includes — is a configure-time dependency.
A change to any of them triggers a CMake reconfigure, which re-evaluates the dependency information and reruns
code generation.
Subsequent builds skip generation entirely until a source file changes.

### Cross-distro compatibility

The macro works across Humble through Lyrical.
It uses `${pkg}_TARGETS` for linking (available since Foxy) and handles distro-specific target name changes
for `generate_parameter_library` dependencies (`tl_expected::tl_expected` on Humble/Jazzy vs `tl::expected` on
Kilted+, `parameter_traits` present on Humble/Jazzy but removed on Kilted+).

## Prerequisites

The generator requires that a nodl document includes exactly one spec with a codegen class type `BASE_CLASS`.

The `nodl_common_interfaces` package provides NoDL descriptions for `rclcpp::Node` and `rclcpp_lifecycle::LifecycleNode`, which are of type `BASE_CLASS`. They are registered as `nodl://rclcpp/node` and `nodl://rclcpp_lifecycle/lifecycle_node`.
Add it as a dependency:

```xml
<depend>nodl_common_interfaces</depend>
```

This is a stopgap: once upstream packages ship their own `.nodl.yaml`, `nodl_common_interfaces` will be deprecated
and replaced by a direct dependency on the upstream package.

## Generated files

The generator produces up to four files, depending on the document's contents:

| File | Always | Contents |
|---|---|---|
| `<target>.hpp` | Yes | Abstract base class header. |
| `<target>.cpp` | Yes | Constructor implementation — creates all handles. |
| `<target>_parameters.yaml` | If parameters | `generate_parameter_library` YAML, converted from NoDL parameters. |
| `<target>_parameters.hpp` | If parameters | `generate_parameter_library` C++ header, generated from the YAML above. |

When using the CMake macro, a `<target>_deps.cmake` file is also written at configure time,
containing the NoDL source paths, ROS package dependencies, and generated file list.

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

And this `CMakeLists.txt`:

```cmake
find_package(ament_cmake REQUIRED)
find_package(nodl_generator_cpp REQUIRED)

nodl_generate_cpp(my_node nodl/my_node.nodl.yaml)

add_executable(my_node_exe src/my_node.cpp)
target_link_libraries(my_node_exe PRIVATE my_node)

ament_package()
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

The user subclasses `MyNodeBase` and implements `on_cmd_vel()`:

```cpp
#include "my_node.hpp"

class MyNode : public MyNodeBase
{
  void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr msg) override
  {
    // Business logic here
  }
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<MyNode>());
  rclcpp::shutdown();
}
```

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

For example, `nodl://rclcpp/node` (provided by `nodl_common_interfaces`) declares itself as a base-class provider:

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

## CLI reference

The CMake macro calls the generator internally, but it can also be used standalone for scripting or debugging.

### Code generation

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

### Dependency discovery

```bash
python -m nodl_generator_cpp \
  --nodl-file my_node.nodl.yaml \
  --output-dir generated/ \
  --target-name my_node \
  --cmake-deps
```

The `--cmake-deps` flag runs the same load → provenance → filter pipeline as the full generator but stops before
template rendering.
It writes a `<target>_deps.cmake` file containing three CMake variables:

| Variable | Contents |
|---|---|
| `<target>_NODL_SOURCES` | Absolute paths to the root NoDL file and every transitive include. |
| `<target>_ROS_DEPS` | Sorted, deduplicated ROS package names needed by the generated code. |
| `<target>_GENERATED_FILES` | The filenames the full generator will produce. |

This is what the `nodl_generate_cpp()` CMake macro calls at configure time to set up `find_package`, file watching,
and the `add_custom_command` output list.

## Relationship to other packages

The NoDL document consumed by this generator is validated by `nodl_schema`.
Include resolution and the document tree are provided by `nodl_schema`'s loader.
The `codegen.cpp` sub-object is opaque to `nodl_schema` — its schema and interpretation are owned entirely by this
package.
`nodl_common_interfaces` registers the base-class NoDL descriptions (`nodl://rclcpp/node`,
`nodl://rclcpp_lifecycle/lifecycle_node`) that the generator's include references resolve against.
For registering a NoDL document with the ament index, see the `ament_nodl` package.
