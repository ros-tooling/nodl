# NoDL composition

Originally, we had designed a concept of "NoDL Fragments" which could be composed together into a full Node Interface.

After some discussion, I have a redesign that removes the concept of a Fragment, instead pulling the holistic Node out to a new level, and considering _all_ NoDL definitions to be potentially partial.

A "Node" is a new schema that we define.

A "NoDL Document" as it currently exists defines "a ROS Node interface", but not necessarily a _whole_ ROS Node's interface.

```yaml
- Node
  - base: Node or LifecycleNode (resolves to a NoDL document somewhere, what we checked in as a "fragment" before)
  - main: in-place NoDL definition for what this node's implementation "owns"
  - mixins: List[NoDL references as ament index locators or relative paths]
```

When "working forward", that is with code generation, the code generator will use the base class, implement the `main`, and ignore the `mixins`.

By having this definition, appropriate documentation can be generated and annotated for the whole node.

Conformance testing can have the whole interface, so an observed node can match it.

When "working backward", we can deduce the `base`, but will not reasonably be able to deduce `mixins`.
That's okay, a Described Node can have the full non-base interface in `main`, and at least get drift detection via conformance testing, and proper documentation.

Please add this new schema, allow for registering it with the ament index, and document it in the Concepts and Schema documentation.
Replace the current fragments concept on this branch.
