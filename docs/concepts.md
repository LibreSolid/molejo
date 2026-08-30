# How it works

This page explains the design rules that make molejo dependable — why
two evaluations of one shape correspond vertex for vertex, exactly
where every vertex sits, and how the two implementations are kept from
drifting apart. You do not need it to *use* molejo; you need it the day
you assert on vertices, unwrap a buffer by hand, or wonder whether the
browser is showing you what your tests tested.

## Declared tessellation, deterministic output

The load-bearing rule of the whole format: **tessellation is declared
in the spec and never adaptive.** `tessellation.profile` vertices
around the profile, `tessellation.path` segments on each element of the
path — counts that never follow geometry or a parameter.

Because the counts are declared, the *shape* of the output — how many
vertices, in what order, joined by which triangles — is a function of
the document alone. Parameter values move vertices and never renumber
them. That buys, for free:

- **vertex correspondence across machine states** — vertex *i* is the
  same material point of the spring at every compression, so
  deformation-aware tooling and tests need no registration step;
- **cheap per-frame animation** — the browser refills one positions
  buffer in place and never rebuilds the index;
- **provable parity** — the two implementations can be compared
  number by number, not just "close enough overall".

The trade is honest: molejo does not refine where curvature is high.
Choose the resolution your consumer needs and declare it.

## The sweep, precisely

A shape is a closed planar profile swept along a path. The conventions
below are the contract both evaluators implement:

- **The start frame.** The path starts at the origin with tangent +Z;
  the profile lies in the plane perpendicular to the tangent, drawn in
  local axes +X and +Y (initially the world's). Fixing this is what
  lets a document describe a shape without also describing where it is:
  **placement belongs to the consumer** — a transform in three.js, an
  assembly placement in a build pipeline.
- **Frame transport is rotation-minimizing.** The profile frame is
  carried along the path by the minimal rotation taking each tangent
  onto the next, composed step by step, so a straight path carries a
  constant frame and no primitive twists the profile except as its own
  geometry demands (a helix's turn is the helix's business).
- **Chains have one start.** No primitive but a `wrap` declares where
  it starts; each begins at the point and frame its predecessor
  reached, and the ring at a joint is sampled once, by the primitive
  that leaves it.
- **Profile sampling.** Circle vertex *j* of *M* sits at angle
  *2πj/M*; a polygon is sampled at its own points, in the author's
  (counter-clockwise) order.

## Vertex and face layout

For an open path of *R* rings and a profile of *M* vertices:

- wall vertex `ring * M + j` — ring-major, profile vertex *j* within
  each ring;
- then the start-cap centre (`R*M`) and the end-cap centre (`R*M + 1`);
- so `V = R*M + 2`.

Faces run walls first (ring-major, then *j*, two triangles per quad),
then the start-cap fan, then the end-cap fan: `F = 2*(R-1)*M + 2*M`.
Winding is outward throughout — the start cap faces −tangent, the end
cap +tangent.

A closed loop (a `wrap`) drops the duplicate ring and both caps: ring
*R−1*'s quads wrap onto ring 0, so `V = R*M` and `F = 2*R*M`.

The ring count follows the document alone: `tessellation.path`
segments are spent on each *element* of the path — one element for a
`line`, `arc` or `helix`; one per declared point for a `spline`; two
per circle for a `wrap` — so a chain of *k* single-element primitives
has `k * path + 1` rings.

## Watertight by construction

A closed profile swept and capped (or closed into a loop) admits no
hole, so there is no repair pass because no input can be broken.
Booleans are deliberately absent: boolean interaction belongs to
whatever mesh machinery consumes the evaluation. Likewise, geometric
sense is the author's obligation — the representation does not police a
self-intersecting sweep or an over-compressed spring, and the
consumer's tests can.

## One spec, two implementations, no drift

The Python and JavaScript evaluators implement the same conventions
with the same arithmetic in the same order, and are held to it by
**shared fixtures** in the repository, which both test suites run:

- **Rejection fixtures** — documents that are not valid specs, with the
  substrings every rejection must name. A validation rule is added once
  as a fixture and paid for twice; in practice the two validators emit
  byte-identical messages.
- **Parity fixtures** — real shapes (a cylinder, an oblique line, a
  quarter bend, a spring, toothed two- and three-pulley belts, filament
  looms) with expected vertices and faces stored per binding. Counts
  and ordering are exact; coordinates pass within a per-runtime
  tolerance. Python compares float64 and its tolerance is headroom for
  a platform's libm; JavaScript writes `Float32Array` positions, so its
  tolerance absorbs single precision — the observed departure is about
  one Float32 ulp.
- **B-rep parity** — every fixture is also evaluated to an exact solid
  and checked on volume and area, both against the mesh (a one-sided
  bound: the inscribed facets always underestimate the smooth solid)
  and against an independently written closed form at 1e-6.

Expectations come from the Python evaluator only after it has passed
its own analytic assertions — watertightness, exact prism volumes,
closed-form belt geometry, the Hermite chain reproduced independently —
so numbers copied from an unvalidated implementation cannot pin a bug
in two languages instead of catching one.

## Errors are part of the contract

The same document fails the same way everywhere: structural faults
raise `SpecError` naming the element by its position in the document;
value faults raise `EvaluationError` naming the parameter and the slot;
unimplemented-but-valid vocabulary raises `NotImplementedError` naming
itself. The messages are byte-identical across the two runtimes, and
the B-rep evaluator shares the mesh evaluator's refusals word for word.
No evaluator ever returns a partial, repaired or quietly degraded
result.
