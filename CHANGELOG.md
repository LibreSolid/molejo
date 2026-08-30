# Changelog

All notable changes to molejo. The Python and JavaScript packages
release together and share one version; each entry covers both.

## 0.2.0 — 2026-08-30

Spec version 2: the reverse bend and the outward tooth face, so a belt
can be driven from *outside* its own circuit. Both packages implement it
in full, and both still read every spec version 1 document unchanged.

The two additions are one thing. A belt held against a pulley by the two
idlers either side of it is bent backwards over that pulley: it reaches
it along its neighbours' internal tangents and hugs it from the far
side, so the loop is concave there and convex everywhere else. Because
the belt turns the other way about that circle, the profile frame turns
with it — and the face that meets the pulley is the outer one. That is
where the teeth have to be, and it is the arrangement the Metamaquina 2
Y axis actually uses, which is where this came from.

### The spec

- `wrap` circles take an optional `turn`: `"clockwise"` (the default, a
  circle inside the loop) or `"counterclockwise"` (a circle the belt is
  bent backwards over). One formula covers both — the v1 external-tangent
  rule with each radius signed by its sense — so the tangent between two
  circles is external where their senses agree and internal where they
  differ. Two circles too close for the tangent their senses call for
  refuse to evaluate, naming which kind is missing.
- `teeth` takes an optional `face`: `"inner"` (the default, the profile
  vertices at the minimum local X, displaced toward the circles) or
  `"outer"` (the vertices at the maximum, displaced away).
- Versioning is now enforced in both directions. A document declaring
  version 1 and using version 2 vocabulary is rejected naming the field
  that forced it; and an author writes the *lowest* version a document
  needs, so a shape asking nothing of version 2 emits the version 1
  document it always did, byte for byte. `molejo.required_version` and
  JavaScript's `requiredVersion` answer that question directly.

### Both evaluators

- Meshes, exact B-rep solids and the JavaScript vertex buffers all
  handle a reverse bend and either tooth face, with the same refusals
  word for word.
- New shared parity fixture `reverse-bend-belt.json`: two bearings
  holding a belt against a pulley whose centre is a parameter, teeth on
  the outer face and circulating with a phase. Both suites run it, and
  the B-rep is checked against a closed form written independently of
  either evaluator.
- New shared rejection fixtures: an unknown `turn`, an unknown tooth
  `face`, and a document that understates its own spec version.

### Compatibility

Spec version 1 documents are read, evaluated and exported exactly as
before; the whole existing fixture set is unchanged. A molejo 0.1.0
installation cannot read a document that uses a reverse bend or an outer
tooth face, and now says so by version rather than by unknown field.

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
