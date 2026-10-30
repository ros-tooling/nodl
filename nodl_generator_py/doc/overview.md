# nodl_generator_py

`nodl_generator_py` generates an `rclpy` base class from a NoDL document.
The generated class creates the declared ROS interfaces.
Application code subclasses it and implements only the node behavior.
`nodl_add_py_executable()`, or a `setup.cfg` section in an `ament_python` package, then generates an executable that runs that class, so `ros2 run` starts it.

Generated files are replaced whenever the `.nodl.yaml` input changes.
Handwritten application code remains separate from generated code.

NoDL and `nodl_generator_py` are build-time dependencies.
The installed generated module imports ROS interfaces, the generated parameter module, and the packages that `nodl_runtime_py` provides.
A deployed application therefore needs `nodl_runtime_py`, but not `nodl_generator_py`.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## CMake integration

`nodl_generate_py(target nodl_file [NO_INDEX] [RESOURCE_NAME name])` is the primary user-facing API for generating base classes:

```cmake
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml)
```

For a project named `echo_robot`, this generates and installs
`echo_robot.generated.echo_node_base.EchoNodeBase`.
The target name must be a valid Python identifier.

### What the function does

| Step | What happens |
|---|---|
| Runtime dependency | Checks that the package declares `nodl_runtime_py` as a runtime dependency. |
| Code generation | Creates the base module during the package build. |
| Build tracking | Regenerates when the root or any transitive NoDL input, generator, schema, or template changes. |
| Build target | Creates an `ALL` custom target named `echo_node_base`. |
| Installation | Installs generated Python modules under `<project>.generated`. |
| Parameters | Delegates parameter-module generation to `generate_parameter_library_py`. |
| Index registration | Registers the full NoDL document with the ament index under `RESOURCE_NAME`, which defaults to the target name. `NO_INDEX` skips this step. |

The application package declares `nodl_generator_py` as a build tool, `nodl_runtime_py` as a runtime dependency,
and every generated ROS interface package as a dependency:

```xml
<buildtool_depend>nodl_generator_py</buildtool_depend>
<exec_depend>nodl_runtime_py</exec_depend>
```

`nodl_generate_py()` fails at configure time without the `nodl_runtime_py` dependency,
since the generated code would fail when it runs.

`nodl_generator_py` depends on `nodl_common_interfaces`, so a package that generates code does not have to explicitly declare it.

### Arguments

| Argument | Description |
|---|---|
| `target` | Build target and generated module name. It is PascalCased directly for the class name, while a trailing `_base` is removed from the runtime node name. `echo_node_base` produces `EchoNodeBase`, running as `echo_node`. |
| `nodl_file` | Absolute path or path relative to the calling `CMakeLists.txt`. |
| `NO_INDEX` | Optional. Do not register the document with the ament index. Giving `RESOURCE_NAME` together with it is an error. |
| `RESOURCE_NAME` | Optional. Name to register the document under. The default is `target`. |

### Index registration

`nodl_generate_py()` registers its document with the ament index, so the node's interface is discoverable as `nodl://<package>/<name>`, where the name is the target name unless `RESOURCE_NAME` overrides it.
The full document is registered as written, including its `codegen` block.

```cmake
nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml)
```

This registers the document as `echo_node_base`.
Renaming the target renames the registered resource, unless `RESOURCE_NAME` is set.
Pass `RESOURCE_NAME` to register under a different name:

```cmake
nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml RESOURCE_NAME echo_node)
```

Pass `NO_INDEX` for a document that should not be registered:

```cmake
nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml NO_INDEX)
```

Giving `RESOURCE_NAME` together with `NO_INDEX` is an error, because the name has no effect.

Each resource name and each document file can be registered once per package.
Two calls that generate from the same document need `NO_INDEX` on all but one of them.

Every `local://` include of the document must be registered in the same package with `ament_nodl_register()`, or configuration fails.
`find_package(nodl_generator_py)` also makes `ament_nodl_register()` available.

## Generated files

The generator produces these files in `<project>/generated`:

| File | When | Contents |
|---|---|---|
| `__init__.py` | Always | Marks the generated package. |
| `<target>.py` | Always | Generated `rclpy` base class. |
| `<target>_parameters.py` | With parameters | Typed parameter listener and values. |

When parameters are present, the build also creates an intermediate
`<target>_parameters.yaml` file for `generate_parameter_library_py`.
The intermediate YAML file is not installed.

## Example

The `echo_robot` package generates a node base class from a NoDL document, subclasses it, and runs the subclass.
It is built and run by the tests of the `test_nodl_generators` package.

The NoDL document declares a parameter, a publisher, and a subscription:

```{literalinclude} examples/echo_robot/nodl/echo_node.nodl.yaml
:language: yaml
:caption: nodl/echo_node.nodl.yaml
```

The handwritten subclass keeps the behavior:

```{literalinclude} examples/echo_robot/echo_robot/echo_node.py
:language: python
:start-at: from std_msgs
:caption: echo_robot/echo_node.py
```

The generated base constructs the publisher, subscription, and parameter listener.
The subclass supplies the subscription callback and application behavior.

The package generates the base class, installs the handwritten module, and adds an executable for the subclass:

```{literalinclude} examples/echo_robot/CMakeLists.txt
:language: cmake
:start-at: cmake_minimum_required
:caption: CMakeLists.txt
```

The package declares the generator as a build tool, `nodl_runtime_py` as a runtime dependency, and each ROS interface package it uses:

```{literalinclude} examples/echo_robot/package.xml
:language: xml
:start-at: <buildtool_depend>ament_cmake</buildtool_depend>
:end-at: <exec_depend>nodl_runtime_py</exec_depend>
:caption: package.xml
```

After building and sourcing the workspace, `ros2 run echo_robot echo_node` starts the node.

## Running a node class

`nodl_add_py_executable(executable target [EXECUTOR ref])` generates an executable that runs a node class, as in the example above.
The executable is a short script that imports the class and calls `nodl_runtime_py.run_node` on it.
`run_node` constructs the node, configures and activates it if it is a lifecycle node, and spins it until SIGINT or SIGTERM.
The script is generated at build time and installed to `lib/<project>`, where `ros2 run <project> <executable>` finds it.
A conformance test can launch it with `nodl_add_conformance_test(... EXECUTABLE <executable>)`.

The class can be any rclpy node class, whether or not it derives from a generated base.

The `target` is a `module:Class` import reference.
The module must be importable from the installed package, for example because the package installs it with `ament_python_install_package()`.
A malformed reference fails the build.

The package must declare `nodl_runtime_py` as a runtime dependency, as for `nodl_generate_py()`, or configuration fails.
The generated script imports it when it runs.

### Choosing the executor

Pass `EXECUTOR` to spin the node with an executor other than the default `SingleThreadedExecutor`.
It is a `module:Class` import reference to a class that takes no arguments:

```cmake
nodl_add_py_executable(echo_node echo_robot.echo_node:EchoNode
  EXECUTOR rclpy.executors:MultiThreadedExecutor)
```

| Argument | Description |
|---|---|
| `executable` | Name of the installed executable. The build target is `nodl_py_executable_<executable>`. |
| `target` | `module:Class` import reference to the node class. |
| `EXECUTOR` | Optional. `module:Class` import reference to the executor class. The default is `rclpy.executors:SingleThreadedExecutor`. |

## ament_python integration

An `ament_python` package cannot call `nodl_generate_py()`, so it declares the same generation in `setup.cfg`.
`nodl_generator_py` extends setuptools, so `setup.py` needs no change.
The extension does nothing for a package whose `setup.cfg` has none of these sections.

The `echo_robot_py` package generates a node base class from a NoDL document, subclasses it, and runs the subclass.
It is built, tested and run by the tests of the `test_nodl_generators_ament_python` package.

The NoDL document declares a parameter, a publisher, and a subscription:

```{literalinclude} examples/echo_robot_py/nodl/echo_node.nodl.yaml
:language: yaml
:caption: nodl/echo_node.nodl.yaml
```

The handwritten subclass keeps the behavior:

```{literalinclude} examples/echo_robot_py/echo_robot_py/echo_node.py
:language: python
:start-at: from std_msgs
:caption: echo_robot_py/echo_node.py
```

`setup.cfg` generates the base class and installs an executable for the subclass:

```{literalinclude} examples/echo_robot_py/setup.cfg
:language: ini
:end-before: "[tool:pytest]"
:caption: setup.cfg
```

For a package named `echo_robot_py`, this generates `echo_robot_py.generated.echo_node_base.EchoNodeBase`,
registers the document with the ament index as `echo_node_base`,
and installs an `echo_node` executable that runs the handwritten `EchoNode` subclass.
The package is built by `colcon build`, with or without `--symlink-install`, by `setup.py build` and `setup.py install`, and by `pip install --no-build-isolation`.
An isolated build environment does not have `nodl_generator_py`, so `pip` builds the package with the sections ignored and without an error.
An editable `pip install` is an error.
`colcon build --symlink-install` needs setuptools older than 80, since colcon does.

The package declares `nodl_generator_py` as a build tool and `nodl_runtime_py` as a runtime dependency, as for CMake:

```{literalinclude} examples/echo_robot_py/package.xml
:language: xml
:caption: package.xml
:start-at: <buildtool_depend>
:end-at: </exec_depend>
```

The build fails without the `nodl_runtime_py` dependency, with the same message as `nodl_generate_py()`.
The package's name in `package.xml` is the Python package that gets the `generated` subpackage, so it must be listed in `packages` in `setup.py` and must not have a `generated` subpackage of its own.

### Generating a document

Each `[nodl_generate_py.<target>]` section has the arguments of `nodl_generate_py()`, and `<target>` is its `target`.

| Option | Description |
|---|---|
| `nodl_file` | Required. Path to the document, relative to `setup.cfg`. |
| `resource_name` | Optional. Name to register the document under. The default is the target. An error together with `no_index`. |
| `no_index` | Optional. `true` does not register the document with the ament index. |

Registration behaves as described under "Index registration" for CMake.
The registered document and its copy under `share/<package>/nodl` have `local://` includes rewritten to `nodl://<package>/<name>`.
Every `local://` include of a registered document must itself be registered in the package with its own section, or the build fails.
The documents are read from the source directory when the package is built, so a source distribution has to include them, for example with a `MANIFEST.in`.

### Installing an executable

Each `[nodl_add_py_executable.<executable>]` section installs a script named `<executable>` next to the package's other scripts.
It is the script that `nodl_add_py_executable()` generates, which "Running a node class" describes.
A script of the same name from `console_scripts` or `scripts` is an error.

| Option | Description |
|---|---|
| `target` | Required. `module:Class` reference to the node class, usually a subclass of a generated base. |
| `executor` | Optional. `module:Class` reference to the executor class, for example `rclpy.executors:MultiThreadedExecutor`. The default is `rclpy.executors:SingleThreadedExecutor`. |

An `ament_python` package installs its scripts under `lib/<package>` for `ros2 run` with the `[develop]` and `[install]` settings in the example.

### What is generated and where

| Output | Location |
|---|---|
| Generated modules | `<package>.generated`, a subpackage of the installed package. |
| Index registration | `share/ament_index/resource_index/nodl/<package>__<name>`, and `share/<package>/nodl/<name>.nodl.yaml`. |
| Executables | `lib/<package>/<executable>`, or wherever `install_scripts` points. |

Everything is generated into `nodl_generated` in the build base, and never into the source tree.
colcon builds outside the source tree.
For `setup.py build` and for `pybuild`, the build base is `build` in the package directory unless `--build-base` says otherwise,
so a read-only source tree needs `--build-base` somewhere else.
A build generates it all again, and removes the modules of a document that was removed from `setup.cfg`.
As with CMake, files that an earlier install put in the install space stay there.

With `colcon build --symlink-install`, edits to the package's files take effect without a build.
A file or directory added to the top level of the package needs another build.

### Testing

A test that runs `python -m pytest` in the package directory imports the package from the source tree, which has no `generated` subpackage.
A `conftest.py` that removes the source directory from `sys.path` makes it import the built package instead.
`testpaths` keeps pytest from collecting the package directory, which would import the source package again.
The `test` directory must not have an `__init__.py`.
With one, pytest puts the package directory back on `sys.path` for every test module, which undoes the `conftest.py`.
A package in a `src` directory, with `package_dir={'': 'src'}` in `setup.py`, does not need the `conftest.py`,
since `src` is not the directory that `python -m pytest` adds to the path.
It still needs `testpaths`, and it can have a `test/__init__.py`.

```{literalinclude} examples/echo_robot_py/test/conftest.py
:language: python
:start-at: import sys
:caption: test/conftest.py
```

```{literalinclude} examples/echo_robot_py/setup.cfg
:language: ini
:start-at: "[tool:pytest]"
:caption: setup.cfg
```

The tests of `test_nodl_generators_ament_python` run the example's tests with and without this `conftest.py`.

## Generated class API

Entity names become Python identifiers by removing leading and trailing `/` characters
and replacing other non-alphanumeric groups with `_`.

| NoDL entity | Generated member or callback | Subclass use |
|---|---|---|
| Publisher | `pub_<name>` | Publish messages. |
| Subscription | `sub_<name>` and abstract `on_<name>(msg)` | Implement the callback. |
| Service server | `srv_<name>` and abstract `on_<name>(request, response)` | Implement the callback. |
| Service client | `cli_<name>` | Send requests. |
| Action server | `action_srv_<name>`, `on_<name>_goal()`, `on_<name>_cancel()`, and abstract `execute_<name>()` | Optionally override admission and cancellation policy; implement execution. |
| Action client | `action_cli_<name>` | Send goals. |
| Parameters | `param_listener_` and `params_` | Read typed parameter values. |

The constructor accepts keyword arguments and forwards them to the selected `rclpy` base class.

## Includes and lifecycle nodes

The file-based CLI and `nodl_generate_py()` resolve the complete include tree.
An included document with `codegen.python` is a provider: it already has an implementation,
so the generator does not generate it or walk into its includes.
A provider with `codegen.python.role: BASE_CLASS` also selects the generated class's base.
A provider with `codegen.python.role: NO_GENERATE` does not select a base:

```yaml
codegen:
  python:
    role: NO_GENERATE
```

`NO_GENERATE` takes no `module`, `class`, or `publisher_method` fields.
Entities supplied by either kind of provider and all of its transitive includes are not generated again.
A `BASE_CLASS` included by a `NO_GENERATE` provider is hidden from the generator.
At most one Python base provider may be visible.
Documents without a visible Python base provider keep the implicit `rclpy.node.Node` base.
The generator rejects `BASE_CLASS` and `NO_GENERATE` on the root document; these roles describe included providers.
Move provider metadata to an included document and omit `codegen.python` on the root.

Use the standard lifecycle provider like this:

```yaml
nodl_version: 2
include:
  - ref: nodl://nodl_common_interfaces/lifecycle_node

publishers:
  - name: status
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE
```

This generates a subclass of `rclpy.lifecycle.LifecycleNode`.
Generated publishers use `create_lifecycle_publisher()`, so they publish only while the node is active.
The constructor still creates all parameters and entities.
Subscriptions, services, clients, and actions do not become lifecycle-managed.

The generator does not emit transition callbacks.
The default `rclpy` callbacks activate and deactivate managed publishers.
If an application subclass overrides a transition callback and wants that default behavior, it must call and return the corresponding `super()` callback:

```python
def on_activate(self, state):
    # Add application-specific activation work before or after this call.
    return super().on_activate(state)
```

## Parameters

NoDL parameters are converted to the YAML format consumed by
[`generate_parameter_library_py`](https://github.com/PickNikRobotics/generate_parameter_library).
Dotted NoDL names remain flat in the source document, while the intermediate YAML is nested as required by genparamlib.
For example, `colour.r` is available as `self.params_.colour.r` and retains `colour.r` as its ROS parameter name.
The generated base obtains the initial typed values during construction:

```python
self.param_listener_ = echo_node_base_parameters.echo_node.ParamListener(self)
self.params_ = self.param_listener_.get_params()
```

## CLI reference

The CMake function and the `ament_python` extension call the generator internally.
The same generator can be run directly for scripting or debugging:

```bash
python -m nodl_generator_py \
  --nodl-file nodl/echo_node.nodl.yaml \
  --output-dir generated/echo_robot/generated \
  --target-name echo_node_base
```

| Flag | Description |
|---|---|
| `--nodl-file` | NoDL document to load. |
| `--output-dir` | Directory for generated files. It is created when absent. |
| `--target-name` | Generated module name. It must be a valid Python identifier. It becomes the class name directly; a trailing `_base` is removed from the runtime node name. |
| `--cmake-deps` | Write `<target>_deps.cmake` with the complete transitive NoDL source list, then exit. Intended for build integration. |

The executable generator has its own entry point, which `nodl_add_py_executable()` and the `ament_python` extension call:

```bash
python -m nodl_generator_py.executable echo_robot.echo_node:EchoNode \
  --executor rclpy.executors:MultiThreadedExecutor \
  --output build/echo_node
```

| Argument | Description |
|---|---|
| `TARGET` | `module:Class` import reference to the node class. |
| `--executor` | Optional `module:Class` import reference to the executor class. |
| `--output` | Write an executable file with mode 0755 instead of printing the script. |

## Current scope

This version supports parameters, publishers, subscriptions, services, actions,
their available QoS settings, include composition, and one included Python base provider.
Lifecycle management applies only to publishers created for a lifecycle base.

## Relationship to other packages

`nodl_schema` loads and validates the input document.
`nodl_generator_common` provides language-neutral entity naming.
`generate_parameter_library_py` generates typed parameter support when required.
The installed result uses `rclpy` and the ROS interface packages named by the document.
