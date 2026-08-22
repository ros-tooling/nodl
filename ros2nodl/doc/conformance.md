# Check conformance from Python

`ros2nodl.conformance` manages the runtime part of a conformance check. It loads
and composes an explicit NoDL file, describes the running node, and passes the
two documents to `nodl_conformance.diff`.

Use `check_conformance` when code must inspect each difference:

```python
from ros2nodl.conformance import check_conformance

differences = check_conformance(
    nodl_file='nodl/my_node.nodl.yaml',
    node_fqn='/robot/my_node',
    timeout_sec=15.0,
)
```

Use `assert_conforms` when an aggregated `AssertionError` is more convenient:

```python
from ros2nodl.conformance import assert_conforms

assert_conforms(
    nodl_file='nodl/my_node.nodl.yaml',
    node_fqn='/robot/my_node',
)
```

The file is the explicit root contract. Its `include` references are resolved
recursively through the standard `nodl_schema` resolvers before the node is
described. An unresolved reference, invalid document, or merge collision stops
the check before runtime observation. A description failure stops comparison.

Description gaps become `unverifiable` differences with their original path and
reason. Semantic differences are aggregated and sorted for stable diagnostics.

This API deliberately does not infer a document from the `nodl_nodes` resource
index and does not add a `ros2 nodl conform` command.
