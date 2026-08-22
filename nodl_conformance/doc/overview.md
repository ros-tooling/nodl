# nodl_conformance

`nodl_conformance` is a small Python library that compares two loaded NoDL
documents. It does not load files, inspect running ROS nodes, or provide launch
integration.

```python
from nodl_conformance import diff

differences = diff(expected, actual, node_fqn='/robot/my_node')
```

`expected` and `actual` are `nodl_schema.NodlDocument` objects. An empty list
means conformance. Each `Difference` contains `kind`, `section`, `name`, and
`detail`. Supported kinds are `missing`, `extra`, `type_mismatch`,
`qos_mismatch`, `property_mismatch`, and `unverifiable`.

## Comparison rules

Comparison is strict. Every declared public interface must be present in the
actual document, and every actual public interface must be declared.

The comparator handles these name forms:

- `/status` stays absolute.
- `status` resolves in the node namespace.
- `~/status` resolves below the full node name.

Short ROS interface types compare equal to their kind-specific fully qualified
form. For example, `std_msgs/String` equals `std_msgs/msg/String` for a topic.

Collection order, empty collections, description fields, and top-level
`codegen` metadata do not affect the result. Publishers, subscriptions, service
servers, service clients, action servers, and action clients remain separate
interface collections.

### QoS

The comparator checks each declared topic QoS policy present in the actual
document. An omitted optional policy places no requirement on the actual
endpoint. `SYSTEM_DEFAULT` and `BEST_AVAILABLE` accept a concrete actual policy.

`KEEP_LAST` requires a matching depth. Other history policies ignore depth. An
omitted duration and zero both mean unlimited. Finite nonzero durations must
match exactly.

### Parameters

The comparator checks parameter name, type, and `read_only`. It ignores
`description`, `default_value`, `additional_constraints`, and validation rules.
The actual current value does not represent the declared default.

A generic actual parameter type cannot prove a declared fixed-size type. This
case produces an `unverifiable` difference.

## Runtime integration

`ros2nodl` loads and composes the expected document, describes a live node, and
calls this comparator.
