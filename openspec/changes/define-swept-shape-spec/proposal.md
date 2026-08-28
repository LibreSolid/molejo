## Why

Mechanical CAD has no representation for the flexible parts of a
machine. A valve spring compresses with cam lift; a timing belt
circulates around its idlers while one span follows the carriage
clamped to it; a cable loom and a filament follow a print head through
X, Y and Z. Each of these shapes is, at any instant, exact closed-form
math over a few scalars — but existing kernels represent rigid
geometry, and animation systems interpolate placement, so a part whose
*shape* is a function of machine state falls between the two.

Sampling the shape does not generalize. Morph targets and frame
swapping work for one parameter and die combinatorially at two or
three: a loom following three axes needs a sampled grid over all of
them, with kernel renders, document weight and memory growing as K^d.
The originating consumer (solid-node, a Python framework for mechanical
CAD whose parts must render in a browser viewer at frame rate and be
geometrically testable in Python) needs one representation whose
evaluation cost is independent of parameter count and whose two
evaluations — build/test and per-frame viewer — provably agree.

## What Changes

molejo is founded as that representation, with five capabilities:

- **spec-schema**: a versioned, JSON-serializable spec: a closed planar
  profile (circle, polygon) swept along a chain of path primitives
  (line, arc, helix, wrap, spline) whose numeric slots are either
  literal numbers or references to named scalar parameters; fixed,
  declared tessellation counts. The spec is the master representation:
  analytic at its core, watertight by construction, deterministic in
  vertex count and ordering.
- **python-evaluator**: spec + `{parameter: number}` → triangle mesh
  (numpy vertices/faces) and STL bytes. This is the exact-evaluation
  side: build pipelines, geometric tests, collision checks.
- **js-evaluator**: the same spec + the same values → vertex buffers
  (`Float32Array` positions, index array) consumable by three.js,
  cheap enough to re-evaluate every animation frame.
- **parity**: shared fixtures under `fixtures/`, run by both suites:
  identical vertex counts and ordering, coordinates within each
  fixture's declared tolerance. A primitive exists only when its
  fixture passes on both sides.
- **distribution**: one repository, two packages — `molejo` on PyPI
  (from `python/`) and `molejo` on npm (from `js/`) — versioned
  together with the spec version they implement.

## Capabilities

### New Capabilities

All five: `spec-schema`, `python-evaluator`, `js-evaluator`, `parity`,
`distribution`. This is the founding change; there is no existing
behavior to modify.

### Modified Capabilities

None.

## Impact

- `python/molejo/` — schema model, validation, path/profile evaluation,
  mesh assembly, STL export.
- `js/src/` — schema parsing and the twin evaluation, emitting typed
  arrays.
- `fixtures/` — parity fixtures, one per primitive plus composed cases.
- Motivating validation cases (exercised by the consumer, recorded here
  as the empirical origin): a helical valve spring compressing with
  lift (1 parameter); a belt loop wrapping fixed idlers with
  circulating teeth and a carriage-anchored span (1 parameter); a cable
  loom / filament run following a moving extruder (3 parameters).

## Out of scope

- Booleans, mesh repair, self-intersection policing, physics solvers
  (a catenary primitive may come later as its own change if a project
  shows designer-controlled splines are not enough).
- Any expression language over parameters: consumers evaluate their
  expressions to numbers before calling molejo.
- A B-rep evaluator. The analytic master makes one possible later
  without a schema change; nothing here depends on it.
