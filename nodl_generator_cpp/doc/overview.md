# nodl_generator_cpp

`nodl_generator_cpp` generates a C++ abstract base class from a NoDL document.
The generated class inherits from the appropriate node type (determined by includes), creates all endpoint handles
in its constructor, and exposes pure-virtual callbacks for inbound endpoints.
You subclass it and write only business logic.

Generated files are never edited by hand — they are regenerated whenever the `.nodl.yaml` changes.
This is the same generate-always pattern used by `rosidl_generator_cpp`.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.
This package implements the "forward" workflow: a NoDL document is the source of truth that makes a node's interface
exist.

## CMake integration

The `nodl_generate_cpp()` CMake macro is the primary user-facing API.
Three lines in your `CMakeLists.txt` are the entire integration surface:

```cmake
find_package(nodl_generator_cpp REQUIRED)

nodl_generate_cpp(my_node_base RESOURCE_NAME my_node nodl/my_node.nodl.yaml)

add_executable(my_node src/my_node.cpp)
target_link_libraries(my_node PRIVATE my_node_base)
```

### What the macro does

`nodl_generate_cpp(TARGET [SHARED|STATIC] [EXPORT] [NO_INDEX] [RESOURCE_NAME name] NODL_FILE)` creates a library target named `TARGET` that you link against.
The library is SHARED unless you pass `STATIC`, as in `nodl_generate_cpp(my_node_base STATIC RESOURCE_NAME my_node nodl/my_node.nodl.yaml)`.
It handles everything:

| Step | When | What happens |
|---|---|---|
| Dependency discovery | Configure time | Reads the NoDL document to find its source files, its ROS package dependencies, and the files the generator will produce. |
| `find_package` | Configure time | Automatically calls `find_package` for every ROS dependency (message, service, action, and base-class packages). |
| Reconfigure on change | Configure time | A change to the NoDL file or any of its includes triggers a reconfigure. |
| Code generation | Build time | Runs the generator, only when an input file has changed. |
| Library creation | Build time | Compiles the generated code into a SHARED (default) or STATIC library with position-independent code, and adds the output directory to the include path. |
| ROS linking | Build time | Links all ROS dependencies of the document. |
| Parameter code | Build time | When the document has parameters, links the libraries that the generated parameter header needs. |
| Index registration | Configure time | Registers the document with the ament index, unless you pass `NO_INDEX`. |
| Install | Install time | Installs a SHARED library to `lib` (`bin` for Windows DLLs) so executables find it at runtime. A STATIC library is only installed with `EXPORT`. |
| Export | Install time | Only with `EXPORT`. Installs the generated headers (including `<target>_parameters.hpp`) to `include/<package>/<package>/` and exports the library as `<package>::TARGET`. The generated `.cpp` and the parameter YAML are not installed. |

### Arguments

| Argument | Description |
|---|---|
| `TARGET` | Name of the library target to create. Used verbatim as the C++ class name (PascalCased) and for all generated filenames, so a `<node>_base` target yields a `<Node>Base` class. A single trailing `_base` is stripped to form the runtime node name (`<node>_base` runs as `<node>`). |
| `SHARED` / `STATIC` | Optional library type. The default is `SHARED`. The type only chooses how the library is built, and does not affect the export. Installed SHARED libraries go to `lib`, which is on the library path of a sourced workspace, and exported STATIC archives go to `lib` too. The library type does not follow `BUILD_SHARED_LIBS`. The library file is named after `<PROJECT_NAME>_<TARGET>`, for example `lib<PROJECT_NAME>_<TARGET>.so`, to avoid collisions between packages, while the CMake target name stays `TARGET`. A target that already starts with the package name gets it twice, so target `my_pkg_base` in project `my_pkg` produces `libmy_pkg_my_pkg_base.so`. Both are built with position-independent code, so a STATIC library can still be linked into a SHARED library such as an `rclcpp_components` plugin. Giving both is an error. |
| `EXPORT` | Optional. Install the headers and export the library to other packages. Without it the library is private to the package. A private SHARED library is still installed to `lib`, because executables need it at runtime, but its headers are not installed. A private STATIC library is not installed at all, because an archive has no runtime role. |
| `NO_INDEX` | Optional. Do not register the document with the ament index. Giving `RESOURCE_NAME` together with it is an error. |
| `RESOURCE_NAME` | Name to register the document under, giving the resource key `<package>__<RESOURCE_NAME>`. Required unless `NO_INDEX` is given, with no default. |
| `NODL_FILE` | Path to the `.nodl.yaml` file, relative to `CMAKE_CURRENT_SOURCE_DIR`. |

### Index registration

`nodl_generate_cpp()` registers its document with the ament index, so the node's interface is discoverable through `nodl://<package>/<RESOURCE_NAME>`.
The full document is registered as written, including its `codegen` block.

```cmake
nodl_generate_cpp(my_node_base RESOURCE_NAME my_node nodl/my_node.nodl.yaml)
```

The resource name is part of the package's public interface, so `RESOURCE_NAME` has no default.
Omitting it is a configure-time error that suggests `RESOURCE_NAME <name>` or `NO_INDEX`.
Pass `NO_INDEX` for a document that should not be discoverable:

```cmake
nodl_generate_cpp(my_node_base NO_INDEX nodl/my_node.nodl.yaml)
```

Giving `RESOURCE_NAME` together with `NO_INDEX` is an error, because the name has no effect.
Registration does not depend on the library type or on `EXPORT`.

`nodl_generator_cpp` depends on `ament_nodl`, and `find_package(nodl_generator_cpp)` also finds `ament_nodl`.
Registration follows the rules of `ament_nodl_register`.
Every `local://` include of the document must itself be registered in the same package or configuration fails.
Each resource name and each document file can be registered once per package.
A package that already registers its public contract with `ament_nodl_register`, and generates from a composition document that includes it with `local://`, registers both under different names.
The basics tutorial does this, with the contract as `talker` and the generator input as `talker_cpp`.
Two calls that generate from the same document need `NO_INDEX` on all but one of them.

(using-a-generated-target)=

### Using a generated library target from another package

A library is private to its package unless you pass `EXPORT`, which works for both library types:

```cmake
nodl_generate_cpp(my_node_base EXPORT RESOURCE_NAME my_node nodl/my_node.nodl.yaml)
```

Downstream packages can then use the target.
They add the exporting package as a dependency in `package.xml`, then link the exported target:

```cmake
find_package(my_package REQUIRED)

add_library(downstream_library SHARED src/downstream_library.cpp)
target_link_libraries(downstream_library PRIVATE my_package::my_node_base)
```

```cpp
#include "my_package/my_node_base.hpp"
```

The exported target automatically carries its ROS dependencies such as `rclcpp` and messages.

The exporting package declares `nodl_generator_cpp` as a `<buildtool_export_depend>`, and the ROS dependencies of its documents as `<depend>` (or `<build_export_depend>`):

```xml
<buildtool_export_depend>nodl_generator_cpp</buildtool_export_depend>
<depend>rclcpp</depend>
<depend>std_msgs</depend>
```

A missing `<depend>` does not break workspace builds, but it breaks rosdep and binary installs.

With `EXPORT`, call `nodl_generate_cpp()` before `ament_package()` in the same `CMakeLists.txt` as `ament_package()`, not inside a function or subdirectory.
Doing so will raise an error, so turn a wrapper function into a macro.
A package can export several libraries, and each is available as `<package>::<TARGET>`.
If the package calls `ament_export_targets()` itself with a custom `NAMESPACE`, that namespace also applies to the generated targets.
A STATIC library linked into several SHARED libraries that are loaded into one process gives each of them its own copy of the class and parameter code.
The `test_nodl_generators_downstream` package in the repository is a tested example of this workflow.

### Including the generated header

The macro passes `--include-prefix ${PROJECT_NAME}`, so headers are generated under a directory named after your package.
Consumers include them by the package-scoped path, following the ROS convention:

```cpp
#include "my_package/my_node_base.hpp"
```

Linking against `TARGET` adds the output directory to your include path, so the include resolves with no further setup.
The prefix is always the project name and cannot be overridden from the macro.
An existing build directory may still hold a stale flat header from older versions, so do a clean build to catch leftover flat includes.

### Rebuild behavior

Every file in the NoDL include tree — the root document and all transitive includes — is a configure-time dependency.
A change to any of them triggers a CMake reconfigure, which re-evaluates the dependency information and reruns
code generation.
Subsequent builds skip generation entirely until a source file changes.

### Cross-distro compatibility

The macro works across all supported ROS distributions.
It handles the differences in dependency target names between distributions, so the same `CMakeLists.txt` works on all of them.

## Prerequisites

The generator requires that a nodl document includes exactly one spec with a codegen class type `BASE_CLASS`.

The `nodl_common_interfaces` package provides shared NoDL descriptions for the standard node and lifecycle-node base types.
Their `codegen.cpp` metadata selects `rclcpp::Node` or `rclcpp_lifecycle::LifecycleNode` as the `BASE_CLASS`.
They are registered as `nodl://nodl_common_interfaces/node` and `nodl://nodl_common_interfaces/lifecycle_node`.
Add the package as a dependency:

```xml
<depend>nodl_common_interfaces</depend>
```

## Generated files

The generator produces up to four files, depending on the document's contents.
Paths are relative to the output directory, and `<prefix>` is the `--include-prefix` value (the package name when using the CMake macro).
Without a prefix, the headers are written to the output directory itself.

| File | Always | Contents |
|---|---|---|
| `<prefix>/<target>.hpp` | Yes | Abstract base class header. |
| `<target>.cpp` | Yes | Constructor implementation that creates all handles. It includes `<prefix>/<target>.hpp`. |
| `<target>_parameters.yaml` | If parameters | Parameter YAML, converted from NoDL parameters and used as the input of the parameter header generator. |
| `<prefix>/<target>_parameters.hpp` | If parameters | C++ parameter header, generated from the YAML above. Its exact contents are produced by the parameter header generator and vary with the installed dependency version, so golden tests assert only that it is generated (existence-only), while byte-comparing the `<target>_parameters.yaml` input we own. |

When using the CMake macro, a `<target>_deps.cmake` file is also written at configure time,
containing the NoDL source paths, ROS package dependencies, and generated file list (with the prefixed header paths).

## Example

Given this NoDL input:

```yaml
nodl_version: 2

include:
  - ref: nodl://nodl_common_interfaces/node

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

And this `CMakeLists.txt`, in a package named `my_package`:

```cmake
cmake_minimum_required(VERSION 3.22)
project(my_package)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_cpp REQUIRED)

nodl_generate_cpp(my_node_base RESOURCE_NAME my_node nodl/my_node.nodl.yaml)

add_executable(my_node_exe src/my_node.cpp)
target_link_libraries(my_node_exe PRIVATE my_node_base)

ament_package()
```

The generator produces this header, written to `my_package/my_node_base.hpp` in the output directory:

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

And this source file, written to `my_node_base.cpp`:

```cpp
// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_package/my_node_base.hpp"

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
#include "my_package/my_node_base.hpp"

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

## Base class and includes

When generating a node, the generator walks the NoDL document tree to find a `BASE_CLASS` role document.
The metadata there informs which base class (`rclcpp::Node`, `rclcpp_lifecycle::LifecycleNode`, or a custom class) this node implementation inherits from.

Included documents' roles inform the generator what entities need to be generated, and which do not.
For example, the base class already provides its interface, so those endpoints should not be created by the generator.

### The `codegen.cpp` metadata

A NoDL document can carry a `codegen.cpp` field describing how it takes part in C++ generation, selected by its `role`:

| Role | Valid on | Fields | Meaning |
|---|---|---|---|
| `BASE_CLASS` | Included documents | `class`, `header` (both required), `publisher_type` (optional) | The document is implemented by a C++ base class that the generated class inherits from. |
| `NO_GENERATE` | Included documents | none | The document has an existing implementation but does not provide the generated class's base. |
| `NODE` | The root document | `namespace` (optional) | The document is the one being generated. |

The schema for this field is defined in {repo}`nodl_generator_cpp/nodl_generator_cpp/schemas/codegen_cpp.schema.yaml`
and validated by `nodl_generator_cpp`, not `nodl_schema`.

For example, `nodl://nodl_common_interfaces/node` declares itself as a C++ base-class provider:

```yaml
# nodl://nodl_common_interfaces/node
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
  - ref: nodl://nodl_common_interfaces/node
publishers:
  - name: /status
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}
```

Use `NO_GENERATE` when an included document has an existing implementation but does not provide the generated class's base:

```yaml
codegen:
  cpp:
    role: NO_GENERATE
```

`BASE_CLASS` and `NO_GENERATE` describe included provider documents, and the generator reports an error if the root carries either.
`NODE` describes the root, and the generator reports an error if an included document it walks into carries it.
A root without `codegen.cpp` is also valid.

### Publisher type

`BASE_CLASS` accepts an optional `publisher_type`, the C++ publisher class template that the base class's `create_publisher` returns.
It defaults to `rclcpp::Publisher`, and `header` must declare it.
`nodl://nodl_common_interfaces/lifecycle_node` sets it to `rclcpp_lifecycle::LifecyclePublisher`:

```yaml
codegen:
  cpp:
    role: BASE_CLASS
    class: rclcpp_lifecycle::LifecycleNode
    header: rclcpp_lifecycle/lifecycle_node.hpp
    publisher_type: rclcpp_lifecycle::LifecyclePublisher
```

The generated class declares each publisher as `<publisher_type><MessageT>::SharedPtr`.
`rclcpp_lifecycle::LifecycleNode::on_activate` and `on_deactivate` activate and deactivate its lifecycle publishers.
A subclass that overrides those callbacks calls the base class's implementation to keep that behavior.

### Namespace

`NODE` accepts an optional `namespace`, which may be nested with `::`:

```yaml
nodl_version: 2
codegen:
  cpp:
    role: NODE
    namespace: my_pkg::nodes
include:
  - ref: nodl://nodl_common_interfaces/node
```

The generated header declares the class inside the namespace, and the source defines the constructor inside it,
so subclasses inherit from `my_pkg::nodes::MyNodeBase`.
The parameter structs live under it too, as `my_pkg::nodes::my_node_base::Params`.
ROS parameter names never include the namespace.
Without a `namespace`, the class is generated in the global namespace.

### Walking the include tree

The generator walks the include tree from the root and decides, for each included document, by its `codegen.cpp`:

| Included document | Generated | Walk continues into its includes |
|---|---|---|
| No `codegen.cpp` | Yes | Yes |
| `role: BASE_CLASS` | No, its class becomes the base | No |
| `role: NO_GENERATE` | No | No |

An included document with `codegen.cpp` is a **provider**: an existing implementation handles it and everything it includes,
so the generator does not look inside.
The root and every document without `codegen.cpp` are merged into the one document the generator scaffolds.

```
root (being generated — no codegen)
 ├── include: nodl://nodl_common_interfaces/node   [BASE_CLASS → provider]
 │    → /rosout, /parameter_events, …               not generated
 └── own: /status                                   scaffolded
```

### Inheritance chains

A base-class provider can itself include another base class.
`rclcpp_lifecycle::LifecycleNode` extends `rclcpp::Node`:

```
root (being generated)
 └── include: nodl://nodl_common_interfaces/lifecycle_node   [codegen: BASE_CLASS → provider]
      └── include: nodl://nodl_common_interfaces/node        [codegen: BASE_CLASS, not visited]
           → /rosout, /parameter_events, …                    provided by lifecycle_node
```

The walk stops at `LifecycleNode`, so it never visits the inner `rclcpp::Node`.
The generator sees exactly one base class, the outermost provider, and inherits from it.

The walk also stops at a `NO_GENERATE` provider.
If it transitively includes a `BASE_CLASS`, that base is hidden from the generator.
The root must include another visible `BASE_CLASS` provider or C++ generation fails with the normal no-base-class error.

### Error: multiple direct base classes

If the root document directly includes two unrelated base-class providers, the generator rejects the input — C++
single-inheritance means it cannot produce a class that inherits from two unrelated node types:

```
root
 ├── include: nodl://nodl_common_interfaces/node             [codegen: BASE_CLASS]
 └── include: nodl://nodl_common_interfaces/lifecycle_node   [codegen: BASE_CLASS]
```

These are siblings, so the walk reaches both.

### No base class

A document that does not include any `codegen.cpp.role: BASE_CLASS` provider is also an error.
Every generated node must inherit from a concrete base.

## Parameters

The C++ parameter structs are generated with [`generate_parameter_library`](https://github.com/PickNikRobotics/generate_parameter_library), which is bundled with `nodl_generator_cpp`.
The NoDL parameter schema is a formalization of its implicit schema, so NoDL parameters convert to it directly.

The generator converts NoDL parameters to a YAML file in that format, then delegates to the library to produce the
C++ parameter header.
Dotted NoDL names remain flat in the source document, while the intermediate YAML is nested as that format requires.
For example, `colour.r` is available as `params_.colour.r` and retains `colour.r` as its ROS parameter name.
No `declare_parameter()` calls appear in the generated templates.

The generated base class holds two protected members for parameter access:

```cpp
protected:
  my_node::ParamListener param_listener_;
  my_node::Params params_;
```

Parameters declared by providers and their includes (e.g. `use_sim_time` from `rclcpp::Node`) are not generated,
and do not appear in the intermediate YAML or the generated header.

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
| `--target-name` | Yes | Used verbatim as the C++ class name (PascalCased) and the stem of all generated filenames. A single trailing `_base` is stripped to form the runtime node name. Must be a valid C++ identifier. |
| `--include-prefix` | No | Place the generated headers under `PREFIX/` in the output directory, and include them by that path. One or more `/`-separated path segments, such as `my_package` or `my_package/detail`. Each segment starts with a letter, digit, or underscore and continues with letters, digits, `_`, `.`, or `-`. Backslashes and the segments `.` and `..` are rejected. The `.cpp` and the parameter YAML stay at the output directory root. Without the flag, headers are written to the output directory itself. |

### Dependency discovery

```bash
python -m nodl_generator_cpp \
  --nodl-file my_node.nodl.yaml \
  --output-dir generated/ \
  --target-name my_node \
  --cmake-deps
```

The `--cmake-deps` flag loads and walks the document the same way as the full generator but stops before
template rendering.
It writes a `<target>_deps.cmake` file containing three CMake variables:

| Variable | Contents |
|---|---|
| `<target>_NODL_SOURCES` | Absolute paths to the root NoDL file and every transitive include. |
| `<target>_ROS_DEPS` | Sorted, deduplicated ROS package names needed by the generated code. |
| `<target>_GENERATED_FILES` | The paths the full generator will produce, relative to the output directory and including `--include-prefix` for headers. |

This is what the `nodl_generate_cpp()` CMake macro calls at configure time to set up `find_package`, file watching,
and the `add_custom_command` output list.

## Relationship to other packages

The NoDL document consumed by this generator is validated by `nodl_schema`.
Include resolution and the document tree are provided by `nodl_schema`'s loader.
The `codegen.cpp` sub-object is opaque to `nodl_schema` — its schema and interpretation are owned entirely by this
package.
`nodl_common_interfaces` registers the shared base-type descriptions (`nodl://nodl_common_interfaces/node`
and `nodl://nodl_common_interfaces/lifecycle_node`) that the generator's include references resolve against.
The macro registers the document with the ament index through the `ament_nodl` package.
