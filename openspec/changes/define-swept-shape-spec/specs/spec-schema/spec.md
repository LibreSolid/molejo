## ADDED Requirements

### Requirement: Serializable analytic swept-shape spec

A molejo shape SHALL be a JSON-serializable document carrying a spec
version, one closed planar profile, one path (a chain of path
primitives), and declared tessellation counts. The spec is the master
representation: evaluators derive meshes from it, and nothing derives
the spec from a mesh.

#### Scenario: A spec round-trips

- **WHEN** a valid spec is serialized to JSON and parsed back
- **THEN** the parsed spec evaluates to the identical mesh

### Requirement: Numeric slots are literals or parameter references

Every numeric slot in a spec SHALL accept either a literal number or a
reference to a named scalar parameter (`{"param": name}`). The spec
SHALL NOT carry arithmetic, expressions, or defaults: consumers
evaluate their expressions to numbers before evaluation.

#### Scenario: A parameter reference is resolved at evaluation

- **WHEN** a spec slot references parameter `lift` and evaluation is
  given `{"lift": 3.2}`
- **THEN** the slot evaluates as the number 3.2

#### Scenario: A dangling reference is rejected

- **WHEN** a spec references a parameter the evaluation call does not
  provide
- **THEN** evaluation fails naming the parameter and the slot, and no
  mesh is produced

### Requirement: v1 vocabulary

Version 1 SHALL define profiles `circle` and `polygon` (closed), and
path primitives `line`, `arc`, `helix`, `wrap`, and `spline`. A
document using any other profile or primitive name SHALL be rejected by
validation naming the unknown element. The vocabulary is closed:
consumers cannot register primitives.

#### Scenario: An unknown primitive is rejected

- **WHEN** a spec names a path primitive outside the v1 vocabulary
- **THEN** validation fails naming it, before any evaluation

### Requirement: Declared, fixed tessellation

Tessellation counts (samples along each path primitive and around the
profile) SHALL be declared in the spec and SHALL NOT depend on
geometry, parameter values, or the evaluating runtime. Vertex count and
ordering SHALL be identical for every evaluation of one spec,
regardless of parameter values.

#### Scenario: Parameter values do not change topology

- **WHEN** one spec is evaluated under two different parameter bindings
- **THEN** both meshes have identical vertex counts, identical face
  arrays, and vertex i corresponds to the same profile/path station in
  both

### Requirement: Watertight by construction

An evaluated mesh SHALL be watertight: the profile is closed, the sweep
is capped at open path ends, and a path declared as a loop closes onto
its own start. Validation SHALL reject a spec whose profile is not
closed.

#### Scenario: An open-ended sweep is capped

- **WHEN** a spec's path starts and ends at distinct points
- **THEN** the evaluated mesh is closed by planar caps and reports
  watertight
