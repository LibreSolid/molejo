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
(closed loop, pattern circulates) only slides the pattern — both over
the same closed loop, since an open belt's two ends meet at the clamp
(see "The wrap" below). v1 flanks
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

**Sweep evaluation conventions.** Settled while implementing the first
vertical slice (tasks 2.1–2.6, 5.1–5.2), and binding on every evaluator
and every later primitive. Parity is a claim about *identical* vertex
ordering, so these are not implementation detail: a fixture generated
under one ordering is worthless under another, and changing any of them
invalidates every fixture at once.

- **The start frame.** A path begins at the origin with tangent `+Z`.
  The profile lies in the plane perpendicular to the tangent, its local
  x and y axes initially world `+X` and `+Y`. A document therefore
  describes a shape without also describing where it is; placement stays
  the consumer's.
- **Transport is rotation-minimizing.** The frame is carried onto each
  new tangent by the minimal rotation and turned about nothing else, so
  a straight path carries a constant frame — exactly, not nearly: equal
  tangents yield the identity matrix, which is what makes the axial
  cylinder bitwise stable. An antiparallel tangent has no minimal
  rotation, so the axis is chosen deterministically rather than
  arbitrarily. Any twist a primitive wants (a helix's) is that
  primitive's own, applied on top of transport.
- **Profile ordering.** Circle vertex *j* of *M* = `tessellation.profile`
  sits at angle `2*pi*j/M`, at `cos*x + sin*y` in the profile frame. A
  polygon's vertices are its declared points in order.
- **Path sampling.** `tessellation.path` is a segment count *N*, spent on
  each path primitive: a chain of *k* primitives is sampled into *k*·*N*
  segments and, open, into *R* = *k*·*N* + 1 rings (see "Chained paths"
  below; for the single primitive of the first slice, *R* = *N* + 1).
- **Vertex indexing.** Wall vertex `ring*M + j`, ring-major. After the
  walls come exactly two more vertices: the start-cap centre, then the
  end-cap centre. So *V* = *R*·*M* + 2.
- **Face ordering and winding.** Walls first, ring-major then *j*, two
  triangles a quad — `(a, b, c)` then `(a, c, d)` for
  `a = ring*M + j`, `b = ring*M + (j+1) mod M`, `c = b + M`, `d = a + M`.
  Then the start-cap fan `(start_centre, (j+1) mod M, j)`, then the
  end-cap fan `(end_centre, last + j, last + (j+1) mod M)`. Winding is
  outward throughout: the start cap faces `-tangent`, the end cap
  `+tangent`. So *F* = 2·(*R* − 1)·*M* + 2·*M*.
- **Output types.** Python emits float64 vertices `(V, 3)` and int32
  faces `(F, 3)`, bitwise identical for a repeated binding. JavaScript
  emits a `Float32Array` of 3·*V* positions and a `Uint32Array` of 3·*F*
  indices — the same triangles in the same order. Single precision is
  the only substantive difference between the runtimes, which is why a
  fixture declares a tolerance per runtime.
- **Buffer reuse.** Because the counts follow the document alone, the JS
  index cannot change for a given spec. `evaluate(spec, values, buffers)`
  given a previous return value refills the positions in place, leaves
  the index untouched, and allocates nothing; a fresh call allocates.

Three questions the slice deliberately did not answer, because guessing
them here would pin them by accident: how *N* is distributed across a
multi-primitive path, how a closed loop joins its ends, and what
`tessellation.profile` means for a polygon whose point count is already
declared. All three are settled below — the first under "Chained
paths", the other two under "The wrap", by the belt that first needed
them.

**Chained paths, arcs, and helices.** Settled while implementing the
curved primitives (tasks 3.1–3.4), and binding on every later one.

- **`tessellation.path` is a count per primitive, not per path.** Each
  primitive in the chain is spent *N* segments, so *k* primitives give
  *k*·*N* segments and *k*·*N* + 1 rings. Distributing one budget across
  the chain in proportion to arc length is not merely rejected but
  forbidden: arc length follows parameter values, so the ring count —
  hence the vertex count and the whole index buffer — would follow them
  too, and fixed tessellation would be a fiction. Any distribution rule
  must be a function of the document alone, and per-primitive is the
  simplest such rule; it also reads identically in the single-primitive
  case the cylinder fixture already pinned. A per-primitive override
  (`{"type": "arc", …, "samples": 24}`) would refine this without
  changing what an unadorned document means, so nothing here forecloses
  it; no project has asked yet, and an unasked-for slot is a second way
  to say the same thing.
- **A joint's ring is sampled once, by the primitive that leaves it.**
  The chain is continuous in position *by construction*, not by
  validation: no primitive declares where it starts. `line` declares
  only `to`, `arc` derives its endpoint by rotating the current point,
  `helix` derives its endpoint from radius, turns and height. So a
  primitive begins at the point the previous one reached, primitive *i*
  contributes rings *i*·*N* … (*i*+1)·*N* − 1, and the last one
  contributes the final ring as well. The frame arriving at a joint is
  the frame the outgoing primitive transports onto its own start
  tangent — exactly the identity when the two tangents agree, since the
  pinned transport is exactly the identity on equal tangents. A
  tangent-continuous chain therefore shows no seam and no twist jump at
  a joint, which is what the quarter-bend fixture asserts at both of
  its joints.
- **Tangent continuity is the author's obligation.** Whether an arc
  leaves along the tangent its predecessor arrived on depends on
  parameter values, so no structural validator could decide it, and
  policing continuity is already a stated non-goal. A kinked joint
  evaluates rather than raising: the shared ring is perpendicular to the
  outgoing tangent, so the incoming primitive's last quad is skewed. The
  result is watertight, deterministic, and visibly wrong, which is the
  honest outcome for a shape the author asked for.
- **Transport along a curved primitive is incremental, ring by ring.**
  Ring *i*'s frame is the previous ring's frame transported onto ring
  *i*'s analytic tangent; no primitive gets a transport rule of its own.
  For an arc this is exact rather than approximate: every tangent of a
  circular arc lies in the plane perpendicular to its axis, so every
  minimal rotation is about that axis, and composing them is the single
  rotation through the total angle. For a helix the tangents trace a
  cone and the composition genuinely depends on *N*, converging to the
  continuous rotation-minimizing frame as *N* grows. Either way each
  ring is perpendicular to the local tangent, which is precisely what
  "the wire does not shear" means; what varies with *N* is the roll
  about the tangent, invisible for a circular profile and pinned by the
  fixtures for any profile that is not. The helix asks for no twist of
  its own: transport onto its inclined tangent is the whole of it.
- **`arc` rotates the current point about an axis line.** Given the
  incoming frame's origin *p*, `center` *c*, `axis` *a* and `angle` θ,
  with â = *a*/|*a*|, the axial part *m* = ((*p* − *c*)·â)â, the radius
  *R* = |(*p* − *c*) − *m*|, the radial unit *u* = ((*p* − *c*) − *m*)/*R*
  and the tangential unit *v* = â × *u*, ring *i* of *N* sits at
  φ = *i*·θ/*N* with

      centre  = c + m + R·(cos φ · u + sin φ · v)
      tangent = sign(θ)·(cos φ · v − sin φ · u)

  and the chain continues from the ring at φ = θ. The turn is
  right-handed about â, and only the component of *p* − *c* across the
  axis turns, so an axis line that does not pass through the plane of
  the profile is as good as one that does. Three degeneracies are
  refused at evaluation, naming the slot: a zero `axis` (nothing to turn
  about), a start point on the axis line (*R* = 0, no circle to run on),
  and a zero `angle` (an arc with no tangent, not a small arc). None is
  a structural fault, because all three can arrive through parameters.
- **`helix` winds about the current tangent.** Given the incoming frame
  (*p*, *x̂*, *ŷ*, *t̂*), `radius` *r*, `turns` *T* and `height` *h*, the
  axis is the line through *A* = *p* − *r*·*x̂* along *t̂*, and ring *i*
  of *N* sits at *u* = *i*/*N*, φ = 2π*Tu* with

      centre  = A + r·(cos φ · x̂ + sin φ · ŷ) + h·u·t̂
      tangent = (2πTr·(−sin φ · x̂ + cos φ · ŷ) + h·t̂) / L
      L       = sqrt((2πTr)² + h²)

  So the helix starts exactly at *p*, winds right-handed about *t̂*
  (*x̂* turning toward *ŷ*), and advances *h* over *T* turns. *L* is the
  constant speed and hence the helix's length, so rings uniform in *u*
  are uniform in arc length. A non-integer *T* is ordinary (a spring's
  6.5 coils), *h* = 0 gives a circle, negative *h* advances backwards
  and negative *T* winds left-handed; *r* ≤ 0 and a helix that goes
  nowhere (*T* = 0 with *h* = 0) are refused naming the slot. The start
  tangent is inclined from *t̂* by the pitch angle atan2(2π*Tr*, *h*), so
  a spring given a straight lead-in has a real kink where it starts
  winding: that is what a helix is, not an evaluator artefact.

**The wrap, its teeth, the polygon profile, and the closed loop.**
Settled while implementing the belt (tasks 4.1–4.3) against the
Metamaquina2 geometry, and binding on every evaluator. The wrap is the
first shape that needs a closed loop and the first that needs a
profile which is not a circle, so those two questions are answered here
rather than invented later.

- **A wrap is planar, and it says where it is.** Every other primitive
  describes a shape without describing where it is; a wrap cannot,
  because its circles are declared as world coordinates. The wrap lies
  in the world XY plane (*z* = 0), the circle centres are points of
  that plane, and the path is the belt's **pitch line**: the declared
  radii are pitch radii, and the author places the profile across that
  line as the belt section does across its own pitch line.
- **A wrap is the only primitive in its path**, structurally. It
  defines its own start frame instead of continuing from the frame it
  is handed, so a chain containing one would have two starts; the
  validator refuses it naming the wrap's position. For the same reason
  a wrap ignores the incoming frame entirely.
- **The wrap frame.** At every station the profile's local *x* is the
  in-plane **outward** normal (away from the circles) and its local
  *y* is world **+Z** (the belt's width direction), with the tangent
  the direction of travel. That triple is right-handed — and therefore
  keeps the pinned outward winding without a special case — only if the
  belt circulates **clockwise seen from +Z**, so that is the pinned
  circulation: *n̂* = rot(+90°)*t̂*, *t̂* = rot(−90°)*n̂*.
- **Traversal: external tangents, outside every circle, in declared
  order.** Between consecutive circles *i* and *j* = *i*+1 (mod *k*)
  the belt runs the external tangent that touches both on the same
  side. With *c* = *C_j* − *C_i*, *L* = |*c*|, *ĉ* = *c*/*L*,
  *ĉ*⊥ = (−*c_y*, *c_x*)/*L* and δ = (*r_i* − *r_j*)/*L*:

      n̂ = δ·ĉ + √(1−δ²)·ĉ⊥        (the shared outward normal)
      t̂ = (n̂_y, −n̂_x)             (the direction of travel)
      P = C_i + r_i·n̂,  Q = C_j + r_j·n̂,  |PQ| = √(L² − Δr²)

  and the arc about *C_j* runs clockwise from the arriving normal to
  the departing one, through *w* = (θ_in − θ_out) mod 2π radians, so
  its length is *r_j*·*w*. The elements of the loop are therefore
  span₀, arc₁, span₁, arc₂, …, span_{k−1}, arc₀ — 2*k* of them — and
  the loop's own origin (*s* = 0, ring 0) is the point where the belt
  leaves circle 0. Listing the circles in an order that is not the
  clockwise circulation of their hull produces a belt that crosses
  itself: evaluable, deterministic, visibly wrong, and the author's
  obligation, exactly as a kinked joint is. Crossed and serpentine
  belts (a side flag per circle) stay a recorded non-goal until a
  project asks.
- **Segments are spent per element, not per wrap.** A wrap of *k*
  circles is 2*k* elements, each spent *N* = `tessellation.path`
  segments, so a wrap has *R* = 2·*k*·*N* rings — a function of the
  document alone, as the distribution rule must be. A tooth-driven
  allocation (`samples_per_tooth` in place of `tessellation.path` on a
  toothed wrap) would also be structural, and is not adopted: it is a
  second way to say what the document already says, it leaves a
  toothless wrap without a rule, and it would make the wrap the one
  primitive whose resolution is declared somewhere else. Rings are uniform
  in arc length within an element (uniform in angle on an arc), and a
  joint's ring belongs to the element that leaves it, as in any chain.
  Segment budget never follows tooth count, span length, or a
  parameter: a param-bound centre (a moving idler) changes tooth pitch
  *length* and nothing else.
- **The closed loop join.** A looped path drops the duplicate ring and
  both caps: the last ring's quads wrap onto ring 0. So *V* = *R*·*M*
  exactly and *F* = 2·*R*·*M*, with the same ring-major vertex order
  and the same two-triangles-a-quad winding as an open sweep, ring
  *R*−1 joining ring 0. Watertight without caps, because there are no
  open ends. Only a wrap path is evaluated as a loop today, and a wrap
  document must declare `loop: true` (structural) so that no document
  lies about the topology it has; `loop: true` on any other path still
  raises naming itself, because closing a general chain needs the end
  frame to come back to the start frame, which rotation-minimizing
  transport does not promise.
- **A planar loop comes back without twist, and it is asserted.** Every
  tangent of a wrap lies in the XY plane, so every minimal rotation of
  the transport is about ±Z; the profile's *y* stays exactly world +Z
  and the frame carried once around the loop returns to ring 0's frame.
  That is a property of the geometry, not an assumption: the suite
  transports the last ring's frame onto ring 0's tangent and demands
  the start frame back.
- **Ring stations are geometric; the belt slides past them.** For every
  other primitive a vertex index names the same material point at every
  binding. A belt's material genuinely moves along its loop, so for a
  wrap a vertex index names the same *station* — the same arc-length
  fraction of the loop from the wrap's own origin — and the teeth
  circulate past it. That is what keeps the index buffer reusable while
  the belt runs, and it is stated rather than quietly implied.
- **Teeth are a periodic trapezoid in arc length.** The period is
  *L*/`teeth.count`, where *L* is the loop's evaluated length: the
  count is an integer over the whole loop, which is exactly what makes
  the pattern close seamlessly at the seam, and what keeps a moving
  idler changing tooth pitch length rather than tooth count.
  `teeth.pitch` is therefore the **nominal** pitch of the belt standard
  the author designed to (GT2's 2 mm), carried in the document for the
  consumer and for the B-rep side; the mesh evaluators do not read it.
  With *u* the fractional position in the period and *d* = min(*u*,
  1−*u*) the distance from the pattern origin,

      m = clamp((0.375 − d)·4, 0, 1)

  so one period is ¼ crest (centred on the origin), ¼ ramp, ¼ root, ¼
  ramp. The pattern origin is a crest centre, which is what makes an
  anchor mean "a tooth is clamped here".
- **Teeth displace the inner face only.** The profile's **inner face**
  is every declared vertex at the exact minimum local *x*; those
  vertices move by −`teeth.height`·*m*(*s*) (inward, toward the
  circles) and every other vertex stays put. So the authored profile is
  the belt band measured at the tooth roots, and the teeth protrude
  from it. The minimum is exact equality, not a tolerance: a profile
  whose inner face is not flat displaces one vertex and looks like a
  spike, which is authorship. Likewise, fewer than about four rings per
  tooth aliases the pattern — with *R* = 2·*k*·*N* rings and
  `teeth.count` teeth, the author owes *N* ≳ 2·count/*k* — and molejo
  does not guard it, for the same reason it does not police continuity.
- **`anchor` and `phase` are alternatives, never both.** Both name the
  pattern's material origin *s*₀ along the loop and a document carrying
  the two is refused structurally. `anchor` = {`span`, `at`} puts the
  origin on a tangent span: `span` is a literal index of a span
  (0…*k*−1, checked structurally against the circle count) and `at` is
  a slot giving the distance from that span's start, so an open belt
  clamped to a carriage binds `at` to the carriage position and its
  teeth stay meshed as the carriage runs. `phase` is a slot in
  arc-length units — belt travel, so a consumer feeds
  pulley_radius·motor_angle — measured from the wrap's own origin in
  the direction of travel. Neither present means *s*₀ = 0. Both
  anchored and unanchored wraps evaluate as the same geometrically
  closed loop: the physical open belt's two ends are clamped at one
  carriage point, so the loop passes through the clamp, and the anchor
  changes where the teeth sit, never whether the mesh closes.
- **Polygon profiles are the declared points, in order, and
  `tessellation.profile` is their count.** A polygon's vertex *j* is
  its *j*-th declared (x, y) point in the profile frame — its
  coordinates are ordinary numeric slots and may be parameter-bound —
  and `tessellation.profile` must equal the number of points, refused
  structurally when it does not. Any other reading (resampling the
  outline, ignoring the count) would make the pinned *V* = *R*·*M*
  formulas false or the declared count a lie. The points must run
  counter-clockwise in the profile frame, as the circle's do, or the
  sweep winds inward; that is the author's obligation, since a
  parameter can flip it.
- **What a wrap refuses at evaluation**, naming the slot, because all
  three can arrive through parameters: a circle of non-positive radius,
  two consecutive circles too close to admit an external tangent
  (*L* ≤ |Δ*r*|, which also catches coincident centres), and a negative
  tooth height.

**The spline, its end tangents, and the loom.** Settled while
implementing the spline (tasks 4.4–4.6) against the filament-loom
validation case, and binding on every evaluator. The loom is a run of
filament or cable with one end fixed at the machine frame's entry — a
fixed point and a fixed entry direction — and the other clamped to the
extruder head, whose position follows three parameters and whose entry
direction is fixed relative to the head, because the filament enters the
extruder from above however the head is standing. The designer needs the
two endpoints hit exactly, the direction controlled at *both* ends, the
sag between them shaped by a few interior points, every coordinate
parameter-bindable, and pure closed-form arithmetic identical in the two
runtimes.

- **The flavour is a cubic Hermite chain: Catmull-Rom inside, clamped at
  the ends.** Weighed against that list, neither candidate answers the
  loom alone:

  - *Catmull-Rom through the designer's points* interpolates, so the
    endpoints and every waypoint are hit exactly, and sag is shaped by
    moving points that are **on** the curve — which is how a designer
    thinks about a cable run. But it gives no end-tangent control at
    all: the tangent at an end is whatever a phantom point or a
    one-sided difference makes it, so the loom's two fixed entry
    directions cannot be stated. It answers everything but the
    requirement the loom exists to make.
  - *Cubic Bézier with explicit tangents* controls both ends exactly,
    but its interior handles are control points **off** the curve.
    Shaping sag then means moving points the curve does not pass
    through, and a run wanting two or three waypoints becomes a
    hand-managed chain of Béziers with the author owing C1 at every
    joint — the representation's job, done by hand.

  v1 takes both halves, which costs nothing because they are the same
  curve. A spline is a chain of cubic Hermite spans through the declared
  points; the tangent at an interior point is the uniform Catmull-Rom
  one, and the tangents at the two ends are declared (the *clamped* end
  condition). Interpolating, C1 by construction, one pass of arithmetic,
  and the end directions under the author's hand.
- **A spline does not declare its start, and `points` are what it runs
  through and toward.** As for every primitive but the wrap, a spline
  begins at the point the path has reached. With that start *P*₀ and the
  declared points *P*₁ … *P*ₙ, the spline has *n* spans, and its end
  point *P*ₙ and end tangent become the chain state. A single declared
  point is an ordinary spline of one span — a cubic Bézier between the
  two ends, which is the loom without a waypoint — so the schema asks
  for at least one, not two.
- **The tangents.** Writing *ŝ* for the declared `start_tangent` and *ê*
  for the declared `end_tangent`, both normalized:

      m_0 = |P_1 - P_0| * ŝ
      m_i = (P_{i+1} - P_{i-1}) / 2                    (0 < i < n)
      m_n = |P_n - P_{n-1}| * ê

  A declared tangent is a **direction**: its length is ignored, exactly
  as `arc.axis`'s is, and the Hermite speed at that end is the adjacent
  chord's — the same scale the Catmull-Rom interior tangents carry, so a
  clamped end is no fuller or flatter than an interior point. What
  varies with the declared vector is where the curve points, which is
  the whole of what the loom asks for.
- **An absent tangent means the thing no literal could say.** Without
  `start_tangent` the spline leaves along the **incoming tangent**, so it
  joins its predecessor C1 and a lead-in line hands over without a kink;
  for the first primitive of a path that is the start frame's +Z.
  Without `end_tangent` it arrives along the final chord *P*ₙ − *P*ₙ₋₁,
  the one-sided end condition, since there is nothing after it to
  continue into. Neither default is a second way to say something the
  document could already state: the incoming tangent depends on
  parameter values (a param-bound lead-in has no writable direction),
  and the final chord does too.
- **A span is an ordinary cubic Hermite.** For span *i* from *P_i* to
  *P*_{*i*+1}, ring *j* of *N* sits at *t* = *j*/*N* with

      centre   = h00*P_i + h10*m_i + h01*P_{i+1} + h11*m_{i+1}
      h00 = 2t³-3t²+1   h10 = t³-2t²+t   h01 = 3t²-2t³   h11 = t³-t²
      velocity = (6t²-6t)*(P_i - P_{i+1}) + (3t²-4t+1)*m_i + (3t²-2t)*m_{i+1}
      tangent  = velocity / |velocity|

  The velocity is *m_i* at *t* = 0 and *m*_{*i*+1} at *t* = 1, and
  consecutive spans share that vector, so the curve is C1 across every
  interior point by construction rather than by the author's care. Frame
  transport is the ordinary ring-by-ring rotation-minimizing one; the
  spline asks for no twist of its own.
- **Segments are spent per span, and the span count is structural.** A
  spline through *n* declared points is *n* spans, each spent
  *N* = `tessellation.path` segments, so a lone spline has *n*·*N* + 1
  rings and a joint's ring belongs to the span that leaves it. This is
  the same refinement the wrap already needed — a wrap of *k* circles is
  2*k* elements, each spent *N* — and it is now stated once for the
  vocabulary: **`tessellation.path` is a segment count spent on each
  *element* of the path, and a primitive's element count is a function
  of the document alone** (1 for `line`, `arc` and `helix`, 2*k* for a
  wrap of *k* circles, *n* for a spline of *n* declared points). The
  length of a `points` list is structural, so no parameter can move a
  ring count. Nothing already pinned moves either: the cylinder, the
  quarter bend and the spring hold no spline, and *n* = 1 reads exactly
  as the unadorned per-primitive rule did.
- **What a spline refuses at evaluation**, naming the slot, because all
  of them can arrive through parameters: two consecutive points that
  coincide (a span of no length, whose tangent has no direction), a
  declared `start_tangent` or `end_tangent` of zero length, an interior
  point whose two neighbours coincide (the Catmull-Rom tangent there
  vanishes — the curve doubling back on itself), and a ring whose
  velocity vanishes inside a span. The last is a cusp the author asked
  for; molejo refuses it rather than dividing by zero, because a NaN
  mesh is not the "deterministic and visibly wrong" that a kinked joint
  is.
- **The K^d claim is structural, not a benchmark.** The loom is the case
  that makes the claim concrete — a shape following three axes at once,
  which a sampled representation could only serve by baking a grid over
  all three — and what molejo asserts is stronger and cheaper to check
  than a timing: every numeric slot is read exactly **once** per
  evaluation, and the arithmetic that follows does not know whether the
  slot held a literal or a parameter. So a fully-parametric loom and its
  fully-literal twin evaluate through the identical number of slot reads
  to bitwise-identical vertices, and evaluation cost follows the declared
  tessellation alone. Nothing anywhere samples a parameter grid; the
  suite asserts that rather than measuring around it.
- **The B-rep side gets the spline exactly.** Span *i* is the cubic
  Bézier with poles *P_i*, *P_i* + *m_i*/3, *P*_{*i*+1} −
  *m*_{*i*+1}/3, *P*_{*i*+1}, and the C1 chain of them is one cubic
  B-spline curve (interior knots of multiplicity 2). So the *path* is
  exact in OCCT, with no fitting and no tolerance; only the swept
  *surface* stays the tolerance-declared approximation recorded above,
  as it is for the helix.

**The OCCT binding, the trihedron law, and what a belt's teeth cost.**
Settled while implementing the B-rep evaluator (tasks 6.1–6.5). This is
where "B-rep compatibility is a vocabulary admission rule" stops being a
promise: every v1 primitive now has its exact construction, and the two
places exactness genuinely runs out are named rather than glossed.

- **The binding is OCP** (`cadquery-ocp`), matching the originating
  consumer's stack, as the `brep` extra of the Python package. `molejo`
  itself depends on numpy alone; `molejo/_occt.py` is the only module
  that imports OCCT and it is imported on first use, so importing molejo,
  evaluating a mesh, or exporting STL never touches a CAD kernel. Asking
  for a solid without the extra raises an `ImportError` naming it, so a
  consumer that would rather fall back to a mesh can catch it as the
  ordinary missing-dependency failure it is. That boundary is tested in a
  checkout that *has* the extra, by hiding `OCP` behind an import hook:
  testing it only where OCCT happens to be missing would mean never
  testing it.
- **The trihedron law is corrected Frenet** — `MakePipeShell.SetMode(False)`
  — which is the Frenet trihedron with its torsion twist removed and so
  reproduces the pinned no-twist transport. Plain Frenet is rejected: it
  rolls with the curve's torsion, which a helix has everywhere. The
  honest limits, stated because a law is only as good as what observes
  it: for a circular profile the roll about the tangent does not change
  the solid at all, and every v1 sweep that carries a circle is therefore
  insensitive to the choice; the one non-circular profile in v1 is the
  belt's, which does not sweep at all (below). Where the mesh's frame is
  the discrete *N*-step composition and the B-rep's is the continuous
  law, the two agree exactly after a line or an arc — every minimal
  rotation there is about one fixed axis — and converge as *N* grows
  after a helix or a spline. So a *helix following a curved primitive*
  would wind from a slightly different *x̂* in the two evaluators; no v1
  fixture does, and the difference is invisible for a circular profile.
  Making the B-rep match the mesh's discrete composition instead would
  make an exact evaluation depend on `tessellation.path`, which is
  exactly the confusion the representation exists to avoid.
- **The spline's B-form is double interior knots and 2*n*+2 poles.** Span
  *i* is the Bézier with poles *P_i*, *P_i* + *m_i*/3, *P*_{*i*+1} −
  *m*_{*i*+1}/3, *P*_{*i*+1}, as recorded above; because consecutive
  spans share *m* at the point between them the chain is already C1, so
  the B-form needs only multiplicity 2, and its poles are the pair
  *P_i* ∓ *m_i*/3 straddling every interior point with *P*₀ and *P*ₙ
  themselves at the clamped ends. A Bézier chain — multiplicity 3, 3*n*+1
  poles — describes the identical curve and is rejected: it would declare
  C0 continuity where the geometry is C1, so the kernel would carry a
  weaker claim than the document makes. The poles come from the mesh
  evaluator's own tangent assembly, so the two evaluators cannot disagree
  about which curve a document names; the B-spline reproduces the closed
  form to 6e-14.
- **A belt is a prism, not a sweep.** A wrap's profile has local *y* =
  world +Z at every station, so a belt of rectangular section is exactly
  the region between the trace of its inner face and the trace of its
  outer one, extruded by the section's width. That is chosen over a pipe
  sweep for two reasons and not merely for elegance: it is the only
  construction that can carry **teeth** at all, because a sweep has a
  constant section by definition; and it keeps the whole belt analytic
  where the geometry is — the outer trace never carries teeth, and on the
  inner one a tooth flank crossing a straight span is still a straight
  line, while a crest or a root crossing an arc is still a circular arc.
  A toothless wrap of any profile still sweeps, and a circular one comes
  back as cylinders and toroidal patches with tolerance zero, which is
  the delta spec's own scenario.
- **A tooth ramp crossing an arc is an Archimedean spiral, and that is
  the one thing in a belt that is approximated.** The modulation is
  linear in arc length and arc length is proportional to angle, so on an
  arc the inner trace is *r* = *a* + *b*θ, which no NURBS holds exactly.
  That piece alone is interpolated — a C2 cubic through points on the
  spiral, so it meets both neighbours exactly and the wire still closes —
  and that piece alone makes a toothed belt declare a tolerance. Rejected
  alternatives: replacing the ramp with its chord is exact geometry but a
  *different shape*, silently flattening a flank the document asked to be
  linear in arc length; and making the ramp linear in angle instead would
  contradict the pinned mesh convention and break parity. Measured, the
  interpolated ramp departs from the true spiral by 2.7e-8 on the
  carriage belt and 4.9e-8 on the three-pulley belt, against a declared
  1e-6. Both fixtures exercise the nuance at every binding — the
  Metamaquina2 belt's arcs are 16 mm of a 452 mm loop and a ramp lands on
  one at both carriage positions — and a belt whose ramps all fall on
  spans declares tolerance zero, which the suite exercises too. The prism
  needs a rectangular section; a toothed belt on any other raises naming
  it, because only a rectangle extrudes the same way at every station.
- **The exactness declaration is checked, not asserted.** A result
  carries `tolerance` = 0.0 or the declared approximation tolerance, and
  a zero is verified against the surface classes the solid actually
  carries before it is returned. "The evaluator SHALL NOT degrade an
  analytically representable sweep" is thereby a property of the code
  rather than of the author's care.
- **The result surface is small and says what it is.**
  `molejo.brep.evaluate(document, values)` returns a `BrepResult` with
  `.solid` (a closed `TopoDS_Solid`), `.tolerance`, `.volume()`,
  `.area()`, `.surfaces()` — each face's class as a plain name, so a
  consumer can check exactness without importing OCCT — and
  `.is_closed()`. `shape.brep(**values)` is the authoring-layer twin of
  `shape.evaluate(**values)`. Both evaluators resolve parameters and
  refuse degeneracies through the same code, so a dangling parameter, a
  non-numeric value, a line that goes nowhere or a wrap with no external
  tangent read character for character alike. Volume and area are
  integrated adaptively to a relative 1e-9: OCCT's default fixed-order
  Gauss integration of a swept B-spline face loses four digits of a
  tube's volume, which would make every property assertion a statement
  about the integrator rather than about the shape.
- **Property parity is per fixture, one-sided, and kept honest by a
  closed form.** A faceted mesh is inscribed in the smooth solid it
  samples, so the fixtures' coordinate tolerances are meaningless here: a
  circle profile of *M* vertices encloses (M/2π)·sin(2π/M) of its circle,
  4.5% short at *M* = 12 and 17% at *M* = 6. Each fixture therefore
  declares its own relative `brep` property tolerance, measured with
  about 30% of headroom, and the suite fails a fixture whose declared
  tolerance exceeds twice its measured margin. Alone that would be a weak
  claim, so it keeps company: the gap must run one way (the exact solid
  is the larger), and the same solid must match an independent closed
  form — the tube volume π*a*²*L*, or for a belt the Green's-theorem area
  between its two traces — to 1e-6, five orders tighter, and be nearer it
  than the facets are. That is what "the B-rep is nearer truth" means as
  an assertion rather than a slogan.

**What the two packages carry, and the npm build step there is not.**
Settled at the distribution batch, which is the first evidence either
question had:

- **Plain ESM for `js/`, no build step for v1.** `js/src/*.js` is what
  npm ships, byte for byte: three modules, no dependencies, no bundler,
  no TypeScript, no generated artifact. The dry-run proves it rather
  than assuming it — a scratch project installs the packed 19 kB tarball
  and evaluates a parity fixture under bare `node` — so a package that
  ever began to need compiling would fail there instead of at a
  consumer. The reasoning: the consumer is a three.js application that
  already owns a bundler and consumes ESM directly, and a build step
  would insert a generated artifact between the source and the fixtures
  that pin it to the Python side. TypeScript was the live alternative
  and is deferred, not rejected: the vocabulary is a JSON document whose
  refusals are runtime messages checked character for character against
  Python's, so compile-time types would sit beside `parseSpec` rather
  than replace it, and hand-written declarations can be added later
  without a build. The question reopens when a consumer needs types or
  the package needs to be something other than what its source already
  is.
- **The licence travels with each package, by the means each packer
  understands.** `python/` symlinks `README.md`, `LICENSE` and `NOTICE`
  to the repository root's — one package directory of a two-package
  repository does not own the project's front page — and setuptools
  dereferences them into real files in both the wheel and the sdist.
  npm's packer silently skips symlinks, so `js/` carries real copies
  instead, named in `package.json`'s `files` because npm auto-includes
  `LICENSE` but not `NOTICE`; the dry-run diffs them against the root's
  so a copy cannot drift unnoticed.
- **Neither package ships the test suite or the fixtures.** The parity
  fixtures are repository data at `fixtures/`, above both package
  directories, and the suites read them from there. A wheel carrying
  them would invite a consumer to depend on a path that is not part of
  the package's promise; an sdist carrying half a suite that cannot find
  them would ship a suite that cannot run. Both dry-runs assert their
  absence, and both smoke tests are handed the fixture path from outside
  precisely because the installed package has no copy to fall back on.

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

- `wrap` residuals, now that "The wrap" above settles the signature,
  the traversal, the loop, the teeth, and the two origins: side flags
  for crossed and serpentine belts (a wrap runs outside every circle
  today), and what to do when the evaluated period *L*/count departs
  from the declared nominal `teeth.pitch` — refuse it, report it,
  or make the tooth pitch-sized and let the root land absorb the
  difference, which is what a stretched belt physically does. The belt
  validation case decides; nothing chooses it early, because the
  document already records both numbers.
- `spline` residuals, now that "The spline" above settles the flavour,
  the end tangents, the span allocation and the refusals: the
  parameterization is the uniform Catmull-Rom one, which overshoots when
  consecutive chords differ wildly in length, and the centripetal
  variant is the known fix — equally closed form, equally parity-safe,
  and a different curve through the same points. The loom's spans are
  comparable in length, so nothing chooses it early; a project with a
  run that bunches its waypoints decides.
- B-rep residuals, now that "The OCCT binding" above settles the
  binding, the trihedron law, the spline's B-form, the belt prism and
  the spiral ramp: a toothed belt of non-rectangular section, which the
  prism cannot extrude and no project has asked for; and the roll a
  *swept* non-circular profile would carry, where the corrected-Frenet
  law is the continuous limit of the mesh's discrete composition rather
  than the same number. Neither is observable in v1 — the only
  non-circular profile is the belt's, and a belt does not sweep — so
  neither is chosen early. A project sweeping a keyed or rectangular
  section along a helix decides the second.
- How a closed loop joins its last ring to its first is settled for a
  wrap (see "The wrap": no duplicate ring, no caps, *V* = *R*·*M*), and
  the wrap's planar path is what makes its end frame come back to its
  start frame. What stays open is `loop: true` on a *general* chain,
  which needs an answer to the frame that does not come back — turn the
  residual roll out over the loop, refuse a chain that does not close,
  or let the seam show. It raises naming itself until a shape needs it.
