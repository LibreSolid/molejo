## Context

The forcing function is dual-runtime evaluation of state-dependent
shape. The originating consumer already crosses the Python/browser
boundary *functionally* for rigid motion — placement serializes as
symbolic expressions a browser evaluator resolves per frame, pinned to
Python by parity fixtures — and no equivalent exists for geometry. No
reusable kernel spans the requirement: OCCT and CGAL do not run in a
lean browser widget; OpenSCAD-WASM re-renders whole models in seconds,
not frames; three.js morph targets are baked evaluations, not a
representation, and sampling explodes as K^d in parameter count.

molejo is therefore a new modelling technology, and this record says so
plainly. The fence that keeps it from becoming "a CAD kernel" is the
whole design.

## Goals / Non-Goals

**Goals:**

- One serializable spec from which both evaluators produce the same
  mesh: identical counts and ordering, coordinates within tolerance.
- Evaluation cost independent of parameter count: no sampling grids.
- Watertight output by construction, deterministic under a fixed seed
  of nothing — same spec, same values, same mesh, forever.
- Per-frame affordability in the browser for meshes of the size
  flexible machine parts need (thousands of vertices).

**Non-Goals:**

- Booleans or any mesh repair: the moment the vocabulary includes
  `difference()`, molejo owns CGAL-class robustness problems in two
  languages. Boolean interaction belongs to the consumer's mesh
  machinery, applied to evaluations.
- Policing self-intersection or continuity. An over-compressed spring
  whose coils pass through each other, or a path whose structure
  switches discontinuously with a parameter, is the author's
  obligation; the consumer's tests can catch both.
- Physics. Splines are designer-controlled; a solver-shaped primitive
  (true catenary) is a future change with its own parity argument.
- An expression language. Parameters are plain named numbers.

## Decisions

**The master is analytic and procedural; meshes are evaluations.** The
spec defines exact surfaces in closed form; every mesh is a sampling at
the declared resolution. This is what keeps the exact-vs-mesh question
about *evaluators* rather than the representation: an exact (B-rep)
evaluator — e.g. an OCCT sweep of the same profile along the same path —
can be added later without touching the schema. Neither package claims
exactness today; consumers get meshes and should report them as such.

**Tessellation is fixed and declared, never adaptive.** Adaptive
(curvature/deflection-based) tessellation is why existing kernels
cannot promise cross-evaluation correspondence: counts follow geometry,
so two parameter values disagree about vertices. Declared counts make
parity provable, make vertex correspondence free (vertex (u, v) is the
same material point at every parameter value), and make the browser
cost predictable. The author chooses resolution; the representation
does not second-guess it.

**Sweeps only, one closed profile per shape.** A closed profile swept
along a path, capped at open ends or closed as a loop, is watertight by
construction; no repair pass exists because no input can be broken.
The v1 vocabulary is the empirically demanded set: `line`, `arc`,
`helix` (spring), `wrap` (belt around circles, with phase and anchor),
`spline` (loom, filament) — and grows only by project evidence, one
primitive per demonstrated need, because each addition is paid for
twice plus a parity fixture.

**Numeric slots are literals or parameter references — nothing else.**
A slot is a number or `{"param": name}`. Arithmetic over parameters
(e.g. pitch derived from free length and lift) is the consumer's
business, evaluated to numbers before molejo is called — in Python by
ordinary code, in a browser by whatever expression layer the consumer
already trusts. This keeps molejo's contract pure (spec + values →
vertices), keeps parity surface minimal, and avoids inventing a second
expression language beside the consumer's.

**Dual implementation over shared-runtime alternatives.** Two rejected
crossings, recorded because they were genuinely weighed:

- *JSCAD as the kernel* (`@jscad/modeling` runs in both runtimes-ish):
  one implementation and perfect parity by identity, but authoring
  leaves Python (a rupture for Python-project consumers) and every
  Python-side test instant shells out to node.
- *Pyodide* (run the Python evaluator in the browser): one
  implementation in the right language, but it welds a lean three.js
  widget to a WASM Python runtime with unproven per-frame latency.

Against those, dual implementation of a deliberately small vocabulary
under a fixture-pinned parity discipline is bounded work — a page of
math per primitive per side — and buys Python authoring, native
per-frame browser evaluation, and a spec that outlives both
evaluators.

**Baked shapes are out of molejo entirely.** Pre-existing flexible
parts that ship as sampled meshes (e.g. an imported printable
mechanism's deformation frames) are a consumer-side rendering mode
(morph targets over their own STLs), not a molejo concern: molejo
represents shapes it can define analytically.

## Open Questions

- `wrap` parameterization: tangent-line/arc wrapping around an ordered
  set of circles is well-defined, but the phase convention (tooth
  pattern circulation) and the open-span anchor (belt clamped to a
  carriage) need concrete signatures; the belt validation case decides.
- Spline flavor for v1: Catmull-Rom through designer points vs cubic
  Bézier with explicit tangents. The loom validation case decides; both
  are pure arithmetic and parity-safe.
- Whether profiles may reference parameters in v1 (a pressurized tube
  bulging) or stay static. Default: static until a project demands
  otherwise.
- npm build tooling for `js/` (plain ESM now; whether TypeScript and a
  build step earn their place before first publish).
