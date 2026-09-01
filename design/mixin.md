# Node-mixin library generation from NoDL

This extends `nodl_generator_cpp` beyond whole-node generation:
producing a **node mixin**, a generated class that attaches a NoDL-described ROS interface to an existing node,
and the ament/CMake glue that turns it into a linkable library target,
usable the way `generate_parameter_library` is used.

## Terminology: node mixins

The current generator output is a full node: a class inheriting `rclcpp::Node` (or `rclcpp_lifecycle::LifecycleNode`),
which owns the node identity and can only be used by subclassing exactly one generated class.

A *node mixin* does not inherit from a node class.
It receives the node interfaces it needs and creates its entities against them.
A node author composes one or more mixins into a single node:

```cpp
class CameraNode : public rclcpp::Node, public CameraDriverMixin, public DiagnosticsMixin
{
public:
  explicit CameraNode(const rclcpp::NodeOptions & options)
  : rclcpp::Node("camera", options),
    CameraDriverMixin(*this),
    DiagnosticsMixin(*this)
  {
  }

protected:
  // override the pure-virtual callbacks declared by the mixins
};
```

This gives the author flexibility the node kind cannot:
several independently-described interfaces (each with its own NoDL document, possibly from different packages)
combine into one process-level node, and the mixin is equally usable held as a member or attached to an existing node.

## Goals

1. A package author can turn a NoDL document into a compiled, linkable library target with one CMake call,
   the way `generate_parameter_library(<target> <yaml>)` works.
2. The generated class is usable with any node-like object:
   it depends on node *interfaces*, not on a concrete node base class.
3. Several mixins compose into one node without coordination between their authors.
4. Generation stays a pure, testable core with a CLI, per the existing package layout;
   CMake only orchestrates.

## Prior art

- `generate_parameter_library`: the CMake macro generates code into the build tree and wraps it in a target
  that downstream targets simply `target_link_libraries` against.
  That call-shape is the model for this design.
  Its `ParamListener` also demonstrates the interface-taking constructor pattern
  (`ParamListener(node_parameters_interface, logger)`), which the mixin uses directly.
- `rclcpp::node_interfaces::NodeInterfaces<Ts...>`: an aggregate of node interface handles,
  implicitly constructible from any node-like object (anything with the matching `get_node_*_interface()` getters).
  This is the idiomatic vehicle for "takes the necessary interfaces".
- `rclcpp` free functions `create_publisher` / `create_subscription` / `create_service` / `create_client`
  and `rclcpp_action::create_server` / `create_client` all have interface-taking overloads,
  so entity creation needs no concrete node.

## Generated class shape (`--kind mixin`)

### Constructors

The main constructor takes exactly the interfaces the document's entities require, no more:

```cpp
class CameraDriverMixin
{
public:
  using NodeInterfaces = rclcpp::node_interfaces::NodeInterfaces<
    rclcpp::node_interfaces::NodeParametersInterface,
    rclcpp::node_interfaces::NodeTopicsInterface>;

  explicit CameraDriverMixin(NodeInterfaces interfaces);

  // Accepts any node-like reference, including `*this` in the composition pattern above.
  template<
    typename NodeT,
    typename = std::enable_if_t<rclcpp::node_interfaces::has_node_base_interface<NodeT>::value>>
  explicit CameraDriverMixin(NodeT & node)
  : CameraDriverMixin(NodeInterfaces(node))
  {
  }

  // Convenience constructors: extract the interfaces and delegate to the main constructor.
  explicit CameraDriverMixin(rclcpp::Node::SharedPtr node);
  explicit CameraDriverMixin(rclcpp_lifecycle::LifecycleNode::SharedPtr node);

  virtual ~CameraDriverMixin() = default;
```

The constrained template constructor is what makes `Mixin(*this)` work in a class deriving from the mixin:
without it, overload resolution prefers the (implicitly deleted, once the mixin holds a `ParamListener`) copy constructor,
because derived-to-base is a standard conversion while node-to-`NodeInterfaces` is user-defined.
The constraint keeps the template out of genuine copy construction,
and the `SharedPtr` convenience constructors cover the common handle types.

The minimal interface set is computed from the entity kinds present:

| Entity kind | Required interfaces |
|---|---|
| publisher, subscription | `NodeParametersInterface`, `NodeTopicsInterface` |
| service server | `NodeBaseInterface`, `NodeServicesInterface` |
| service client | `NodeBaseInterface`, `NodeGraphInterface`, `NodeServicesInterface` |
| action server | `NodeBaseInterface`, `NodeClockInterface`, `NodeLoggingInterface`, `NodeWaitablesInterface` |
| action client | `NodeBaseInterface`, `NodeGraphInterface`, `NodeLoggingInterface`, `NodeWaitablesInterface` |
| parameters | `NodeParametersInterface`, `NodeLoggingInterface` |

The union is emitted in a fixed canonical order so output is deterministic.
A document with no entities and no parameters is an error: there is nothing to mix in.

### Body

Everything else keeps the node-kind conventions:

- Entity handle members with the same names (`pub_*_`, `sub_*_`, `srv_*_`, `cli_*_`, `action_*_`).
- Pure-virtual callbacks for inbound entities (`on_*`), overridden by the subclass.
- Entities are created in the constructor via the interface-taking `rclcpp` / `rclcpp_action` free functions.
- Parameters use `generate_parameter_library` unchanged:
  `param_listener_` is constructed from `get_node_parameters_interface()` and the logger from `NodeLoggingInterface`.
- The `NodeInterfaces` aggregate is stored as a protected member `node_interfaces_`,
  so subclass business logic can reach the same interfaces without re-plumbing them.

### Semantics that differ from the node kind

- **No base class.**
  A `codegen.cpp` `role: BASE_CLASS` provider in the include tree is an error under `--kind mixin`:
  the host node provides the base entities, and describing them belongs in the *node's* NoDL document, not the mixin's.
- **Name resolution is deferred to the host node.**
  Relative and private (`~/`) names in the mixin's document resolve against the node the mixin is constructed with.
  This is a feature: the same mixin instantiates under different node names and namespaces.
- **Node identity is not created.**
  `target_name` names the files, the class, and the parameter namespace; it is not a node name.

### Known limitation: lifecycle-managed entities

Publishers created through the interface-taking free functions are plain `rclcpp::Publisher`s,
not `rclcpp_lifecycle::LifecyclePublisher`s, even when the mixin is attached to a `LifecycleNode`.
Lifecycle-managed entity creation and transition wiring is deferred (see Deferred work);
the documentation must state this plainly.

## CLI

The flat CLI grows subcommands (pre-1.0, no compatibility shim):

- `python -m nodl_generator_cpp generate --nodl-file F --output-dir D --target-name T [--kind {node,mixin}]`
  (default `node`, preserving current behavior).
- `python -m nodl_generator_cpp manifest --nodl-file F --target-name T --kind K`
  prints a JSON object describing what `generate` *would* do, without writing anything:

```json
{
  "outputs": ["camera_driver_mixin.hpp", "camera_driver_mixin.cpp",
              "camera_driver_mixin_parameters.yaml", "camera_driver_mixin_parameters.hpp"],
  "inputs": ["/abs/path/camera_driver.nodl.yaml", "/abs/path/included.nodl.yaml"],
  "ros_dependencies": ["rclcpp", "rclcpp_lifecycle", "sensor_msgs", "generate_parameter_library"]
}
```

- `outputs`: exact filenames, resolving the "parameters files only when parameters exist" conditionality.
- `inputs`: every file in the resolved include tree, for correct rebuild dependencies.
- `ros_dependencies`: packages the generated code needs at compile/link time —
  `rclcpp` always, `rclcpp_lifecycle` always for a mixin (the convenience constructor),
  `rclcpp_action` when actions are present,
  the package of every referenced interface type,
  and `generate_parameter_library` when parameters are present.

The manifest is what makes the CMake layer thin: all NoDL knowledge stays in Python.

## CMake integration

A new `cmake/` directory in `nodl_generator_cpp` (it is already an `ament_cmake` package), exporting:

```cmake
nodl_generator_cpp_add_mixin_library(<target> NODL_FILE <path>)
```

which:

1. Runs `manifest` at configure time via `execute_process`.
2. Adds the manifest `inputs` to `CMAKE_CONFIGURE_DEPENDS`,
   so edits that change the manifest itself (new entity types, new parameters) re-run CMake.
3. `find_package`s each entry in `ros_dependencies`
   (they must already be declared in the caller's `package.xml`; a missing one fails with a clear message).
4. Declares an `add_custom_command` producing the manifest `outputs` under
   `${CMAKE_CURRENT_BINARY_DIR}/nodl_generator_cpp/<target>/include/`,
   depending on the manifest `inputs`, so day-to-day NoDL edits rebuild without reconfiguring.
5. Creates `add_library(<target> <generated .cpp>)` (honoring `BUILD_SHARED_LIBS`),
   with the generated include dir as a `BUILD_INTERFACE` include directory,
   linked against the found dependencies' modern CMake targets.

The function does not install or export the target;
installing headers and exporting is the caller's decision, and the usage documentation shows the pattern.
Mixins consumed inside the defining package (the common case) need nothing further.

A future `..._add_node_executable` for the node kind can reuse the same manifest/generate machinery; it is out of scope here.

## Testing

- Generator (Python): mixin variants of the golden cases (pub/sub, services, actions, parameters, kitchen sink),
  plus error tests (BASE_CLASS provider under mixin kind, empty document).
- Manifest: unit tests asserting outputs/inputs/dependencies for representative documents.
- CMake: a new `test_nodl_generator_cpp` package that exercises the real build:
  two mixin NoDL documents, two generated library targets,
  one node class composing both, and a gtest that constructs it and observes the expected endpoints.
  This is the compile-level proof that the composition pattern works.

## Phasing

Each phase is one PR, stacked, independently green:

1. **Design**: this document.
2. **Generator**: `--kind mixin` in the Python core — subcommand CLI, mixin templates,
   interface-set computation, golden and error tests.
3. **Build integration**: the `manifest` subcommand, the CMake function, and `test_nodl_generator_cpp`.
4. **Documentation**: rewrite `nodl_generator_cpp` docs around the node/mixin distinction,
   introducing the node-mixins terminology and the composition usage pattern.

## Deferred work

- Lifecycle-managed entities (LifecyclePublisher creation and lifecycle transition wiring for mixins).
- Install/export helper for shipping a mixin library to downstream packages.
- A CMake entry point for the node kind (executable or component library).
- Timers and other entities NoDL does not yet describe.
- Callback-group control per entity (all entities currently use the default group).
