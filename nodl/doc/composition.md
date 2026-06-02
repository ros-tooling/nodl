
## Composition

A node document may declare a `base` (one of `node` or `lifecycle_node`) and a list of `fragments` to compose its interface from reusable pieces.
At resolution time, the resolver loads the base, then each fragment in the order they are declared, then the main document; later layers win on duplicate names.

Fragments themselves are flat:
they cannot declare a `base` or their own `fragments`.
Nested composition is intentionally disallowed in v2.
If a real need surfaces, the constraint can be lifted without a schema change.
