# Diff

Compare two NoDL documents without observing a running node:

```console
ros2 nodl diff EXPECTED ACTUAL [--node-name NODE_NAME]
```

Both documents are loaded, validated, and resolved before the existing semantic comparison is applied.
The command ignores representation-only changes such as collection order and reports interface changes in stable order.

```console
$ ros2 nodl diff released.nodl.yaml proposed.nodl.yaml
[missing] publishers '/status': expected type 'std_msgs/msg/String' was not observed
```

Relative and private interface names require a node identity before they can be compared with absolute names.
The command uses `/node` by default.
Pass the deployment name when its namespace or private name affects the comparison:

```console
ros2 nodl diff released.nodl.yaml proposed.nodl.yaml --node-name /robot/controller
```

The command exits zero when the documents have the same effective interface, one when semantic differences exist,
and two when a document cannot be loaded or the comparison cannot be performed.

This is an offline document comparison.
Use [`ros2 nodl conform`](conformance.md) to compare a document with a running node.
