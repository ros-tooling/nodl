# Conform

Check whether a running node conforms to an explicit NoDL document:

```console
ros2 nodl conform NODE_NAME --file FILE [--timeout SEC] [--ignore RULE ...]
```

```console
ros2 nodl conform /robot/my_node --file nodl/my_node.nodl.yaml
```

The file is the explicit root contract. Its `include` references are resolved
recursively through the standard `nodl_schema` resolvers before the node is
described. An unresolved reference, invalid document, or merge collision stops
the check before runtime observation. A description failure stops comparison.

Description gaps become `unverifiable` differences with their original path and
reason. Semantic differences are aggregated and sorted for stable diagnostics.

## Ignoring endpoints

The check fails on any endpoint that the document does not declare.
Declaring every endpoint in the document is the goal.
Ignore rules cover two cases:

- **Environment injection.**
  The runtime environment adds an endpoint to every node, which no node document can declare.
  Specifically, `rmw_stats_shim` adds a `/topic_statistics` publisher at the RMW layer, and no other such case is known.
  Set these rules once in `NODL_CONFORMANCE_IGNORE`, next to the environment that injects the endpoint.
- **Partial adoption.**
  A node's helpers, mixins or plugins contribute endpoints that NoDL does not model yet.
  Document the node's own interface and ignore the known contributed endpoints, so conformance tests pass during adoption.
  This is an on-ramp and not a destination, because the contributed endpoints stay unverified until they are declared.
  Pass these rules with `--ignore`, the `ignore` argument of `conformance_test`, or the `IGNORE` argument of `nodl_add_conformance_test`, because they are specific to one node.

Keep rules as narrow as possible, with exact names rather than broad globs where practical.
An ignored endpoint is observed on the running node, so the check reports it as `extra`.
`--ignore` leaves it out:

```console
ros2 nodl conform /robot/my_node --file nodl/my_node.nodl.yaml --ignore publisher:/topic_statistics
```

A rule is `KIND:NAME` or `KIND:NAME:TYPE`, and `--ignore` can be repeated.
`KIND` is `publisher`, `subscription`, `service_server`, `service_client`, `action_server`, `action_client`, or `parameter`.
`NAME` is a glob over the fully qualified name, where `*` also matches `/`.
`TYPE` is an optional glob over the full type, such as `std_msgs/msg/String`.

A rule only drops `extra` differences.
An endpoint that the document declares is still compared in full, and a declared endpoint that is not observed is still `missing`.
The command lists what the rules left out, after `conforms` on success and after the differences on failure:

```text
/robot/my_node: conforms
  ignored [extra] publishers '/topic_statistics': observed undeclared type 'rosgraph_monitor_msgs/msg/TopicStatistics'
```

The rules belong to the check and not to the document.
Unverifiable gaps in the description of an ignored endpoint are still reported.

### Environment default

`NODL_CONFORMANCE_IGNORE` holds whitespace-separated rules that apply to every check run through `ros2 nodl conform` or a test from `nodl_add_conformance_test` or `conformance_test`.
Use it for environment injection, and set it once next to the `RMW_IMPLEMENTATION_WRAPPER=rmw_stats_shim` that adds the endpoint:

```console
export RMW_IMPLEMENTATION_WRAPPER=rmw_stats_shim
export NODL_CONFORMANCE_IGNORE=publisher:/topic_statistics
```

Rules from the environment come before `--ignore` rules.
`assert_conforms` and `check_conformance` never read it.
Pass `ros2nodl.conformance.ignore_from_environment(os.environ)` as `ignore` to apply it from your own code.
`conformance_test` reads it when the test runs.

In Python, `assert_conforms` and `check_conformance` take the same rules as `ignore=[...]`.
`assert_conforms` returns the report, whose `ignored` list holds what the rules left out.

## Exit status

The command exits zero when the node conforms. Otherwise, it prints every
difference and exits nonzero. It does not infer a document from the `nodl_nodes`
resource index.

## Conformance tests

`ros2nodl.testing.conformance_test` runs the same check as a test.
It starts an executable, waits for the node, and fails with every difference from the document.
The `nodl_add_conformance_test` CMake macro of `ament_nodl` generates its test from this function.
A package that does not build with CMake, such as an `ament_python` package, calls it from a test module.

Add the dependency to `package.xml`:

```xml
<test_depend>ros2nodl</test_depend>
```

`colcon` runs `pytest` for an `ament_python` package only if the package declares it where `colcon` looks, such as `extras_require={'test': ['pytest']}` in `setup.py`.
Without it, `colcon test` skips the test.

Create a test module, such as `test/test_conformance.py`, that assigns the two names `launch_testing` looks for:

```{literalinclude} examples/conformance_example.py
:language: python
:start-at: from ros2nodl.testing
```

The example runs against the fixture node of `test_ament_nodl`.
In your package, `package` and `executable` name the executable that your `setup.cfg` or `setup.py` installs.
`pytest` runs the module with the package's other tests, such as `colcon test --packages-select my_package`, and the `launch_test` command of `launch_testing` runs it as well.

The `nodl` argument names the document, in one of two forms.
A **path** is absolute, and is usually built from the test file, such as `nodl=Path(__file__).parent / 'nodl' / 'my_node.nodl.yaml'`.
A **reference** is a `nodl://<package>/<name>` string, which the registered `nodl_schema` resolvers resolve through the ament index.
The document must be installed before the test runs, and it can come from a different package than the executable.

The call checks its arguments, the files they name, and the reference when the module is imported.
A mistake raises there, and `pytest` reports a collection error that interrupts the whole test session of that package, not only this test.

### Arguments

All arguments are keywords.

:`package`: Package containing the executable. Required.
:`executable`: Name of the ROS 2 executable to launch. Required.
:`nodl`: The expected NoDL document, as an absolute path or a `nodl://<package>/<name>` reference. Required.
:`node_name`: Node name passed to the executable and used to construct its fully qualified name. Defaults to `executable`, which must then be a valid node name.
:`node_namespace`: Namespace passed to the executable. Defaults to `/`.
:`timeout`: Maximum time in seconds for the conformance check, a positive integer. Defaults to 15.
:`parameters`: List of `name:=value` items passed to the node as `-p` arguments, applied after `parameters_files`.
:`parameters_files`: List of absolute paths of YAML parameter files passed to the node.
:`ignore`: List of ignore rules, as for `--ignore`.
  Rules in `NODL_CONFORMANCE_IGNORE` apply as well, after these.

The function returns `(generate_test_description, TestNodlConformance)`, both named after the module that calls it.
`generate_test_description` carries the `launch_test` marker, without which `pytest` runs the test case and launches nothing.

The `nodl_add_conformance_test` macro takes the same options, with these differences.
The macro names the node after the test, and the helper names it after the executable.
Paths must be absolute, because a test module has no source directory to resolve against.
`package` is required, because there is no `PROJECT_NAME`.
See the {external+nodl:doc}`ament_nodl guide <_generated/packages/ament_nodl/overview>` for the macro.

See the module source at {repo}`ros2nodl/ros2nodl/testing.py`.
