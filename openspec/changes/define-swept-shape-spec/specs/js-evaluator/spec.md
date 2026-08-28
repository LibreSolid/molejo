## ADDED Requirements

### Requirement: Spec plus values to vertex buffers

The JavaScript package SHALL evaluate a valid spec plus a
`{parameter: number}` mapping to typed arrays directly consumable by
three.js: `Float32Array` positions and an integer index array.
Evaluation SHALL be deterministic under a fixed binding.

#### Scenario: Buffers feed a BufferGeometry

- **WHEN** a cylinder spec is evaluated in JS
- **THEN** the returned arrays describe the same triangles as the
  Python evaluation of the same spec and binding

### Requirement: Per-frame affordability

Re-evaluating a spec under new parameter values SHALL allocate no more
than the output buffers and SHALL be cheap enough to run per animation
frame for meshes of the declared-tessellation sizes flexible machine
parts use (thousands of vertices). The package SHALL support writing
into caller-provided buffers so a viewer can reuse allocations across
frames.

#### Scenario: Re-evaluation into an existing buffer

- **WHEN** a caller passes the buffers from a previous evaluation of
  the same spec
- **THEN** evaluation fills them in place and allocates no new arrays

### Requirement: Loud failure, no partial output

Evaluation SHALL throw naming the offending element and SHALL NOT
return partial buffers, mirroring the Python evaluator's failure
contract.

#### Scenario: A dangling parameter in the browser

- **WHEN** a spec references a parameter the call does not provide
- **THEN** evaluation throws naming the parameter and writes nothing
