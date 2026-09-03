# Conform

Check whether a running node conforms to an explicit NoDL document:

```console
ros2 nodl conform NODE_NAME --file FILE [--timeout SEC]
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

The command exits zero when the node conforms. Otherwise, it prints every
difference and exits nonzero. It does not infer a document from the `nodl_nodes`
resource index.
Use `ament_nodl` when a package needs a CMake-registered launch test.
