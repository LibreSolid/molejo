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
