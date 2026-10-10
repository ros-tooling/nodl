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
  Pass these rules with `--ignore` or the `IGNORE` argument of `nodl_add_conformance_test`, because they are specific to one node.

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

In Python, `assert_conforms` and `check_conformance` take the same rules as `ignore=[...]`.
`assert_conforms` returns the report, whose `ignored` list holds what the rules left out.

## Exit status

The command exits zero when the node conforms. Otherwise, it prints every
difference and exits nonzero. It does not infer a document from the `nodl_nodes`
resource index.
Use `ament_nodl` when a package needs a CMake-registered launch test.
