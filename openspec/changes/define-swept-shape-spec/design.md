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
about *evaluators* rather than the representation: the B-rep evaluator
below consumes the same schema the mesh evaluators do, and nothing in
the schema knows which kind of evaluation it will feed.

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

**Teeth are path modulation with a declared count.** A toothed belt is
the constant cross-section profile swept along the wrap, with teeth as
a declared periodic pattern displacing the profile's inner face along
arc length. The count is declared, so tooth count — hence vertex count
and ordering — never varies with parameters; the anchor (open belt
clamped to a carriage, arc-length origin at the clamp) or phase
(closed loop, pattern circulates) only slides the pattern. v1 flanks
are trapezoidal: piecewise-linear teeth keep every face of a toothed
belt analytic in B-rep (planes, cylinder and torus patches); curved
HTD-style flanks would drop tooth surfaces into the B-spline class and
wait for a project to demand them. Pilot-approved working answer for
the wrap signature (tasks 4.1–4.2 confirm against Metamaquina2
geometry):

    Wrap(
        around=[dict(center=(0.0, 0.0), radius=5.1),      # motor pulley
                dict(center=(0.0, 210.0), radius=5.1)],   # idler
        teeth=Teeth(pitch=2.5, height=0.7, flank="trapezoid", count=180),
        anchor=dict(span=0, at=P.y),   # open: ends clamped to carriage
    )                                  # closed loop: phase=P.travel instead

The motor, gear, and pulley stay consumer-side: one driver (motor
angle) feeds the rigid pulley rotation, the rigid carriage translation,
and the belt's `y` through the consumer's own expressions, so teeth
stay meshed with no constraint solving.

**Numeric slots are literals or parameter references — nothing else.**
A slot is a number or `{"param": name}`. Arithmetic over parameters
(e.g. pitch derived from free length and lift) is the consumer's
business, evaluated to numbers before molejo is called — in Python by
ordinary code, in a browser by whatever expression layer the consumer
already trusts. This keeps molejo's contract pure (spec + values →
vertices), keeps parity surface minimal, and avoids inventing a second
expression language beside the consumer's.

**B-rep compatibility is a vocabulary admission rule.** The
originating consumer's testing architecture asserts on exact shapes,
so molejo must fit it, not merely permit it. Every v1 primitive maps
to an exact OCCT curve — `line` and `arc` as edges, a `wrap` chain as
tangent line/arc edges, `helix` as a curve on a cylindrical surface,
`spline` as a B-spline curve — and a primitive enters the vocabulary
only with both its closed-form mesh math (twice) and its exact B-rep
construction defined. The B-rep evaluator is an optional extra of the
Python package (the browser never needs OCCT). Exactness is stated
honestly: sweeps along lines and arcs produce analytic surfaces
(planes, cylinders, toroidal patches — the entire belt case), while
sweeps along helix and spline paths are tolerance-declared B-spline
surfaces, because no kernel has a closed form for them; that is the
same fidelity class OCCT gives any swept feature. B-rep output carries
no vertex contract, so its parity with the mesh evaluators is
property-based: volume and area against each fixture's expectations.

**Python-first authoring; JSON is the representation.** Authors write
shapes in Python — vocabulary constructors (`Circle`, `Helix`, …) plus
the `P.name` parameter-reference accessor — and `to_json()` emits the
canonical document. JSON is the interchange both evaluators consume: a
hand-written document is equally valid, and the JS package stays
evaluation-only with no authoring layer. The sugar cannot smuggle in an
expression language: a parameter reference refuses arithmetic and
comparison operators with an error telling the author to compute the
number in ordinary Python and bind it at evaluation.

**Validation is structural, total, and locates the offending element.**
Settled while implementing the schema (tasks 1.1–1.5), and binding on
both runtimes:

- Validation needs no parameter values. It answers one question — is
  this a v1 molejo document — and stops at the *first* offending
  element, naming it by its position in the document
  (`path[1].to[2]`, `tessellation.profile`, `path[0].teeth.flank`).
- A dangling parameter reference is therefore *not* a structural error;
  it is an evaluation error. The schema model instead exposes the set
  of names a document references (`Shape.params` in Python,
  `parameterNames` in JS) so a caller can see what it must bind.
- The vocabulary is closed at every level: profile types, path
  primitive types, tooth flanks — and unknown *fields* are rejected
  wherever they appear, not only at the top level. A typo cannot be
  silently ignored by an evaluator that happens not to read that slot.
- The counts that fix topology — `tessellation.path`,
  `tessellation.profile`, `teeth.count`, and `anchor.span` — are
  literal integers and may never be parameter references. A parametric
  count would make vertex count follow a parameter, which the
  fixed-tessellation decision forbids; rejecting it structurally means
  no evaluator has to.
- `loop` is optional on input (default false) and always emitted by the
  authoring layer, so the canonical document is unambiguous.
- Error messages are identical in both runtimes, not merely equivalent:
  values are described by JSON kind ("a string", "an object") rather
  than by any runtime's type names. The shared fixtures assert the
  substrings that matter; message identity is what the fixtures make
  cheap to keep.

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

- `wrap` residual details (the working answer above settles the
  shape): whether `anchor` and `phase` are separate slots or one
  convention, side flags for crossed/serpentine belts, whether
  `samples_per_tooth` replaces `path_samples` on toothed wraps, and
  whether `Teeth(count=…)` is declared free-standing or validated
  against wrap length; the belt validation case decides.
- Spline flavor for v1: Catmull-Rom through designer points vs cubic
  Bézier with explicit tangents. The loom validation case decides; both
  are pure arithmetic and parity-safe.
- Whether profiles may reference parameters in v1 (a pressurized tube
  bulging) or stay static. Default: static until a project demands
  otherwise.
- npm build tooling for `js/` (plain ESM now; whether TypeScript and a
  build step earn their place before first publish).
- The sweep frame convention — how the profile is transported along
  the path (rotation-minimizing vs Frenet, and the tie-break on
  straight segments) — must be pinned once and shared by all three
  evaluators, including MakePipeShell's trihedron law on the B-rep
  side. The arc and helix fixtures decide.
- Which OCCT binding the `brep` extra depends on (OCP is the working
  assumption, matching the originating consumer's stack).
