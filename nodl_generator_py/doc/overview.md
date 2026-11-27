# nodl_generator_py

`nodl_generator_py` generates an `rclpy` base class from a NoDL document.
The generated class creates the declared ROS interfaces.
Application code subclasses it and implements only the node behavior.

Generated files are replaced whenever the `.nodl.yaml` input changes.
Handwritten application code remains separate from generated code.

NoDL and `nodl_generator_py` are build-time dependencies.
The installed generated module imports ROS interfaces, the generated parameter module, and the packages that `nodl_runtime_py` provides.
A deployed application therefore needs `nodl_runtime_py`, but not `nodl_generator_py`.

For what a NoDL document declares, see {external+nodl:doc}`concepts`.

## CMake integration

`nodl_generate_py(target nodl_file [NO_INDEX] [RESOURCE_NAME name])` is the primary user-facing API:

```cmake
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml)
```

For a project named `my_robot`, this generates and installs
`nodl_generated.my_robot.echo_node_base.EchoNodeBase`.
The target name must be a valid Python identifier.

### What the function does

| Step | What happens |
|---|---|
| Runtime dependency | Checks that the package declares `nodl_runtime_py` as a runtime dependency. |
| Code generation | Creates the base module during the package build. |
| Build tracking | Regenerates when the root or any transitive NoDL input, generator, schema, or template changes. |
| Build target | Creates an `ALL` custom target named `echo_node_base`. |
| Installation | Installs generated Python modules as `nodl_generated.<project>`. |
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

(index-registration)=

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

Generated modules install as `nodl_generated.<package>.<target>`, for both CMake and `ament_python`.
`nodl_generated` is a namespace shared by every package, so the modules of many packages import together, and a package's own Python package keeps its name.
Tests and application code import the installed modules without any setup.

The generator produces these files in `nodl_generated/<package>`:

| File | When | Contents |
|---|---|---|
| `__init__.py` | Always | Marks the generated package. |
| `<target>.py` | Always | Generated `rclpy` base class. |
| `<target>_parameters.py` | With parameters | Typed parameter listener and values. |

When parameters are present, the build also creates an intermediate
`<target>_parameters.yaml` file for `generate_parameter_library_py`.
The intermediate YAML file is not installed.

## Example

Given this NoDL document:

```yaml
nodl_version: 2

parameters:
  greeting:
    type: string
    default_value: hello

publishers:
  - name: echo_out
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE

subscriptions:
  - name: echo_in
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE
```

Add the generator to the package's `CMakeLists.txt`:

```cmake
find_package(ament_cmake REQUIRED)
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml)

ament_package()
```

Keep behavior in a handwritten subclass:

```python
from nodl_generated.my_robot.echo_node_base import EchoNodeBase
from std_msgs.msg import String


class EchoNode(EchoNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(
            String(data=f'{self.params_.greeting}: {msg.data}')
        )
```

The generated base constructs the publisher, subscription, and parameter listener.
The subclass supplies the subscription callback and application behavior.

## ament_python integration

An `ament_python` package cannot call the CMake function, so it opts in from `setup.py`.
`nodl_generate_py()` declares a document, and `nodl_cmdclass()` returns the `cmdclass` that generates the declared documents when the package builds.

```{literalinclude} examples/echo_robot_py/setup.py
:language: python
:start-at: import xml
:caption: setup.py
```

For a package named `echo_robot_py`, this generates and installs `nodl_generated.echo_robot_py.echo_node_base.EchoNodeBase`.
The generated files are the ones listed under "Generated files".
The `echo_robot_py` example package uses the NoDL document of the example above.

| Argument | Description |
|---|---|
| `target` | Generated module name, as for the CMake function. It must be a valid Python identifier and unique within the package. |
| `nodl_file` | Path to the document, relative to the directory the build runs in, which is the package directory. |
| `no_index` | Optional keyword. Do not register the document with the ament index. Giving `resource_name` together with it is an error. |
| `resource_name` | Optional keyword. Name to register the document under. The default is `target`. |

`nodl_generate_py('echo_node_base', 'nodl/echo_node.nodl.yaml', resource_name='echo_node')` registers the document as `nodl://echo_robot_py/echo_node`.

`nodl_cmdclass(*documents, cmdclass=None)` takes one or more documents.
A package that has its own command classes passes them as `cmdclass={'build_py': MyBuildPy}`, and they are extended in place of the setuptools defaults.

The package declares `nodl_generator_py` as a build tool, which `setup.py` imports, and `nodl_runtime_py` as a runtime dependency, as for CMake:

```{literalinclude} examples/echo_robot_py/package.xml
:language: xml
:caption: package.xml
:start-at: <buildtool_depend>
:end-at: </exec_depend>
```

The build fails without the `nodl_runtime_py` dependency, with the same message as `nodl_generate_py()`.
The package's name in `package.xml` names the generated package, `nodl_generated.<package>`.
`setup()` must list a package or module, because the generated modules install with `build_py`, which setuptools does not run without one, and the build fails otherwise.
Errors are reported as `error: nodl_generator_py: ...`, and one in a document names its file.

The modules are generated into the build directory, never into the source tree, and installed as `nodl_generated.<package>`.
Each build generates them again, and drops the modules of a document that was removed from `setup.py`.

### Registering documents

Documents are registered with the ament index as for CMake, see [Index registration](#index-registration) above.
The installed files are the same, `share/ament_index/resource_index/nodl/<package>__<name>` and `share/<package>/nodl/<name>.nodl.yaml`.
They install as data files, so the build fails when documents are registered and `setup()` lists no `data_files`.
The package's resource marker is one.
A `local://` include of a registered document is rewritten to `nodl://<package>/<name>`.
The included file must be registered in the same package as well, or installing the package fails.
Each resource name and each document file can be registered once per package, and `nodl_cmdclass()` fails otherwise.
Declare a second module for the same file with `no_index=True`.

### Running a node class

A generated module is a library, so the package writes the entry point itself.
`main()` runs the node class with `nodl_runtime_py.run_node`, which spins it until SIGINT or SIGTERM and returns the exit code.
A `console_scripts` entry calls it as `sys.exit(main())`, and so does running the module directly.

```{literalinclude} examples/echo_robot_py/echo_robot_py/echo_node.py
:language: python
:start-at: from nodl_runtime_py
:caption: echo_robot_py/echo_node.py
```

```{literalinclude} examples/echo_robot_py/setup.py
:language: python
:start-at: entry_points
:end-at: entry_points
:caption: setup.py
```

`ros2 run` finds executables in `lib/<package>`, so `setup.cfg` installs the script there:

```{literalinclude} examples/echo_robot_py/setup.cfg
:language: ini
:caption: setup.cfg
```

After building and sourcing the workspace, `ros2 run echo_robot_py echo_node` starts the node.
The `test_ament_python_example` test of `nodl_generator_py` builds, tests and runs the example package.

### Limitations

`colcon build --symlink-install` generates into the install space, never into the source tree.
Edits to existing files of the package take effect without a rebuild.
A changed document, or a new top-level file or directory in the package, needs a rebuild.
Outside colcon, `setup.py develop` installs the generated modules into its install directory, as `nodl_generated/<package>`, and `setup.py develop --uninstall` removes them.
`--symlink-install` needs a setuptools older than 80, as colcon does.
Editable installs with pip are not supported.
The index and share files of a document that is removed from `setup.py` stay in the install space until it is cleaned, as for any colcon data file.
Deleting the build directory but not the install directory likewise leaves the modules of removed documents in place for a symlink install.

## Generated class API

Entity names become Python identifiers by removing leading and trailing `/` characters
and replacing other non-alphanumeric groups with `_`.

| NoDL entity | Generated member or callback | Subclass use |
|---|---|---|
| Publisher | `pub_<name>` | Publish messages. |
| Subscription | `sub_<name>` and abstract `on_<name>(msg)` | Implement the callback. On a lifecycle base `sub_<name>` is a `Managed` member and the subscription exists only while the node is active. |
| Service server | `srv_<name>` and abstract `on_<name>(request, response)` | Implement the callback. On a lifecycle base `srv_<name>` is a `Managed` member and the service exists only while the node is active. |
| Service client | `cli_<name>` | Send requests. On a lifecycle base `cli_<name>` is a `Gated` member, and `get()` returns the client only while the node is active. |
| Action server | `action_srv_<name>`, `on_<name>_goal()`, `on_<name>_cancel()`, and abstract `execute_<name>()` | Optionally override admission and cancellation policy; implement execution. |
| Action client | `action_cli_<name>` | Send goals. On a lifecycle base `action_cli_<name>` is a `Gated` member, and `get()` returns the client only while the node is active. |
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

`NO_GENERATE` takes no `module`, `class`, `publisher_method`, or `lifecycle` fields.
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

This generates a subclass of `nodl_runtime_py.lifecycle.LifecycleNode`, which derives `rclpy.lifecycle.LifecycleNode`.
Generated publishers use `create_lifecycle_publisher()`, so they publish only while the node is active.
The constructor creates all parameters, publishers and action servers, and creates or registers the subscriptions, services and clients as described below.

### Endpoints of lifecycle nodes

`BASE_CLASS` accepts an optional `lifecycle` boolean, false by default.
`nodl://nodl_common_interfaces/lifecycle_node` sets it to true:

```yaml
codegen:
  python:
    role: BASE_CLASS
    module: nodl_runtime_py.lifecycle
    class: LifecycleNode
    publisher_method: create_lifecycle_publisher
    lifecycle: true
```

A generated node with a `lifecycle: true` base creates its subscriptions and service servers when the node activates and destroys them when it deactivates.
Each `sub_<name>` and `srv_<name>` member is a `nodl_runtime_py.managed.Managed`, which `__init__` constructs with the same type, name, QoS and `on_<name>` callback as a node that is not a lifecycle node.
Its destroy function is `destroy_subscription` for a subscription and `destroy_service` for a service server.
The member only holds the endpoint, so use `on_<name>` to handle messages and requests.
Subscriptions are created in the order they appear in the NoDL document, then service servers in theirs, ahead of the members of an authored subclass.

Each service client and action client exists for the lifetime of the node, and the node hands it out only while it is active.
Each `cli_<name>` and `action_cli_<name>` member is a `nodl_runtime_py.gated.Gated`, which `__init__` constructs around a client created with the same type and name as a node that is not a lifecycle node, and with the same QoS for a service client.
`get()` returns the client while the node is active and `None` otherwise, so the authored class checks the result before it calls:

```python
if (client := self.cli_trigger.get()) is not None:
    client.call_async(std_srvs.srv.Trigger.Request())
```

Because the client exists from construction, it is discoverable and matches its server while the node is inactive.
A call made from `handle_activate` right after startup can still precede that discovery, so wait for the server with `client.wait_for_service()` (`client.wait_for_server()` for an action client) first, or call from a timer or a callback that runs later.
Every `Gated` member registers an activation slot, so service clients are registered in document order, then action clients, after the subscriptions and service servers.

The class named by `class` must be or derive from `nodl_runtime_py.lifecycle.LifecycleNode`, as the node in `nodl://nodl_common_interfaces/lifecycle_node` is.
Otherwise constructing the generated node raises `AttributeError`.
The `nodl_runtime_py` overview describes when the endpoints are created and destroyed relative to the lifecycle hooks.

Subscriptions and service servers are the only endpoints created on activation.
Publishers and action servers are created in the constructor as for any other node.

A `transient_local` subscription of a lifecycle node receives its latched messages after the node activates, and not while it is unconfigured or inactive.
A service server of a lifecycle node is not discoverable, and serves no request, while the node is unconfigured or inactive.
While the node is unconfigured or inactive its subscriptions and service servers are absent from the graph, so conformance of such a node needs it configured and activated first.

Migration: `BREAKING CHANGE:` a node derived from `nodl://nodl_common_interfaces/lifecycle_node` no longer has its subscriptions or service servers while it is unconfigured or inactive.
Messages published in those states, including latched messages, are not delivered to the `on_<name>` callbacks until the node activates.
A service request sent in those states is not served, and a client does not find the service until the node activates.

Migration: `BREAKING CHANGE:` the service clients and action clients of such a node are `Gated` members and no longer `rclpy` clients.
Replace `self.cli_x.call_async(req)` with `if (client := self.cli_x.get()) is not None: client.call_async(req)`, and the same for `self.action_cli_x`.
`get()` is `None` while the node is unconfigured or inactive, so calls are not sent in those states.

The generator does not emit transition callbacks.
The base class seals the `on_*` callbacks, so an authored subclass that defines one raises `TypeError`.
It overrides the `handle_*` hooks instead, and the base class keeps the standard behavior, such as activating the lifecycle publishers:

```python
def handle_activate(self, state):
    # Add application-specific activation work.
    return TransitionCallbackReturn.SUCCESS
```

The `nodl_runtime_py` overview describes the hooks and the order of the transitions.
To move a handwritten lifecycle node to a generated one, see [Migrating a handwritten lifecycle node](https://nodl.readthedocs.io/en/latest/migrating-lifecycle-nodes.html).
A package that generates a lifecycle node declares `nodl_runtime_py` as an `exec_depend`, as for any generated Python node.

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

The CMake function and the `ament_python` build call the generator internally.
The same generator can be run directly for scripting or debugging:

```bash
python -m nodl_generator_py \
  --nodl-file nodl/echo_node.nodl.yaml \
  --output-dir generated/nodl_generated/my_robot \
  --target-name echo_node_base
```

| Flag | Description |
|---|---|
| `--nodl-file` | NoDL document to load. |
| `--output-dir` | Directory for generated files. It is created when absent. |
| `--target-name` | Generated module name. It must be a valid Python identifier. It becomes the class name directly; a trailing `_base` is removed from the runtime node name. |
| `--cmake-deps` | Write `<target>_deps.cmake` with the complete transitive NoDL source list, then exit. Intended for build integration. |

## Current scope

This version supports parameters, publishers, subscriptions, services, actions,
their available QoS settings, include composition, and one included Python base provider.
Lifecycle management applies only to publishers, subscriptions, service servers, service clients and action clients created for a lifecycle base.

## Relationship to other packages

`nodl_schema` loads and validates the input document.
`nodl_generator_common` provides language-neutral entity naming.
`generate_parameter_library_py` generates typed parameter support when required.
The installed result uses `rclpy` and the ROS interface packages named by the document.
