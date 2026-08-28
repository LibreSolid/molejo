## ADDED Requirements

### Requirement: Spec plus values to mesh

The Python package SHALL evaluate a valid spec plus a
`{parameter: number}` mapping to a triangle mesh exposed as numpy
arrays (float vertices, integer faces). Evaluation SHALL be
deterministic: one spec and one binding always produce the identical
arrays.

#### Scenario: Deterministic evaluation

- **WHEN** the same spec is evaluated twice under the same binding
- **THEN** the vertex and face arrays are bitwise identical

### Requirement: Python-first authoring layer

The Python package SHALL provide constructors mirroring the v1
vocabulary and a parameter-reference accessor (`P.name`) from which a
shape serializes to the canonical JSON document. An authored shape and
the document it serializes to SHALL evaluate identically. A parameter
reference SHALL reject arithmetic and comparison operations with an
error directing the author to compute numbers outside the spec.

#### Scenario: Authoring round-trips through JSON

- **WHEN** a shape authored with constructors is serialized with
  `to_json` and parsed back
- **THEN** both evaluate to bitwise-identical arrays under the same
  binding

#### Scenario: Parameter sugar refuses arithmetic

- **WHEN** an author writes `P.free_length - P.lift`
- **THEN** it raises naming the no-expressions rule, and no spec slot
  is produced

### Requirement: STL export

The Python package SHALL export an evaluation as binary STL bytes. The
exported STL SHALL describe the same watertight mesh as the arrays.

#### Scenario: An evaluation becomes an STL

- **WHEN** a cylinder spec is evaluated and exported
- **THEN** an independent STL reader loads a watertight mesh whose
  volume matches the analytic volume within the declared tolerance

### Requirement: Loud failure, no partial output

Evaluation SHALL fail with an error naming the offending element —
unknown primitive, dangling parameter, non-numeric value — and SHALL
NOT return a partial or repaired mesh under any failure.

#### Scenario: A non-numeric parameter value

- **WHEN** evaluation is given `{"lift": "high"}`
- **THEN** it raises naming `lift` and produces no mesh
