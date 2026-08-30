# Changelog

All notable changes to molejo. The Python and JavaScript packages
release together and share one version; each entry covers both.

## 0.1.0 — 2026-08-30

The first release. Spec version 1, implemented in full by both packages
except where noted.

### The spec

- The molejo document: a closed planar profile swept along a parametric
  path at a declared tessellation, serialized as JSON. Every numeric
  slot — coordinates included — is a number or a parameter reference
  `{"param": "<name>"}`; there is no arithmetic in a spec and no default
  for a parameter.
- Profiles: `circle`, `polygon`.
- Path primitives: `line`, `arc`, `helix`, `spline`, and `wrap` — a belt
  path around ordered circles, optionally toothed, with an `anchor` or a
  `phase` to place the tooth pattern.
- Structural validation with position-addressed errors
  (`path[1].to[2]`, `tessellation.profile`), byte-identical between the
  two implementations and pinned by shared rejection fixtures.

### Python (`molejo` on PyPI)

- Authoring layer: `Shape`, `Circle`, `Polygon`, `Line`, `Arc`, `Helix`,
  `Spline`, `Wrap`, `Teeth`, and the parameter accessor `P`, mirroring
  the JSON one-to-one; `to_json`/`from_json` round-trip the canonical
  document.
- Mesh evaluator: spec plus `{name: number}` values to a deterministic,
  watertight triangle mesh (float64 numpy vertices, int32 faces) and
  binary STL. Depends on numpy alone.
- B-rep evaluator (`pip install molejo[brep]`): the same documents to
  closed OCCT solids with an honestly declared tolerance — `0.0` when
  every surface is analytic, `1e-6` where a helix or spline sweep has no
  closed form. Same refusals, word for word, as the mesh evaluator.

### JavaScript (`molejo` on npm)

- Evaluation-only twin: `parseSpec`, `validate`, `parameterNames`, and
  `evaluate(spec, values, buffers)` filling reusable Float32/Uint32
  buffers shaped for three.js `BufferGeometry`, cheap enough to
  re-evaluate every animation frame. Plain ESM, no dependencies, no
  build step.

### Parity

- Both evaluators emit the same vertex count in the same order by
  construction, held to it by shared parity fixtures (a cylinder, an
  oblique line, a quarter bend, a spring, toothed two- and three-pulley
  belts, filament looms) with per-runtime tolerances, and by shared
  rejection fixtures for validation.

### Known limitation

- `loop: true` on a path that is not a `wrap` is valid v1 vocabulary
  that no build closes yet; both evaluators raise `NotImplementedError`
  naming it.
