# The spec

A molejo shape is a JSON document. This page is the reference for spec
**version 1** — every field, every rule, and the errors that enforce
them. The Python authoring layer ({doc}`python`) emits exactly this
document; the JavaScript evaluator ({doc}`javascript`) consumes exactly
this document; a hand-written spec is exactly as good an input as an
authored one.

```json
{
  "molejo": 1,
  "profile": {"type": "circle", "radius": 2.0},
  "path": [{"type": "helix", "radius": 14.0, "turns": 6.5,
            "height": {"param": "height"}}],
  "loop": false,
  "tessellation": {"path": 240, "profile": 16}
}
```

A document describes a **closed planar profile swept along a parametric
path, sampled at a declared tessellation**. It does not describe where
the shape is: every path starts at the origin with tangent +Z, and
placement belongs to the consumer ({doc}`concepts`).

## Top-level fields

| Field | Required | Meaning |
|---|---|---|
| `molejo` | yes | The spec version. This implementation reads and writes `1`. |
| `profile` | yes | The closed planar profile to sweep. |
| `path` | yes | An array of at least one path primitive. |
| `loop` | no | Whether the path closes into a loop. Defaults to `false`. |
| `tessellation` | yes | The declared sampling resolution. |

Unknown fields are rejected, at the top level and inside every object:
the vocabulary is closed so that two implementations cannot quietly
diverge on what they ignore.

## Numeric slots and parameters

Every numeric slot — coordinates included — is either a finite JSON
number or a **parameter reference**:

```json
{"param": "height"}
```

That is the whole parameter mechanism. There is no arithmetic in a
spec, no expression language, and no default for a parameter: consumers
evaluate their expressions to numbers and bind them at evaluation time.
A document's referenced names can be listed without values
(`parameter_names` in Python, `parameterNames` in JavaScript); a
referenced name left unbound at evaluation is an error naming the
parameter and the slot that references it.

## Profiles

The profile is drawn in the plane perpendicular to the path, in the
frame's local X/Y. Its vertex order must run counter-clockwise seen
from ahead (along the sweep direction), or the sweep winds inward —
the circle's does by construction; a polygon's is the author's.

### `circle`

```json
{"type": "circle", "radius": 2.0}
```

A circular profile. `radius` must resolve to a positive number. The
mesh evaluators sample it at `tessellation.profile` vertices, vertex
*j* of *M* at angle *2πj/M*; the B-rep evaluator keeps the true circle.

### `polygon`

```json
{"type": "polygon", "points": [[-0.4, -3.0], [0.9, -3.0], [0.9, 3.0], [-0.4, 3.0]]}
```

A closed polygon through at least three `[x, y]` points, in order. Its
coordinates are ordinary numeric slots, so a profile may be driven by
parameters like anything else.

A polygon is sampled at its own points, no more and no fewer, so
`tessellation.profile` **must equal the point count** — any other
reading would make the declared count a lie.

## Path primitives

A path is a chain: no primitive but a `wrap` declares where it starts.
Each begins at the point (and frame) the previous one reached, and the
whole path begins at the origin with tangent +Z. Angles are in radians.

### `line`

```json
{"type": "line", "to": [0.0, 0.0, 46.8]}
```

A straight segment to the `[x, y, z]` point `to`. Its end must not
coincide with its start.

### `arc`

```json
{"type": "arc", "center": [10.0, 0.0, 0.0], "axis": [0.0, 1.0, 0.0],
 "angle": 1.5707963267948966}
```

A circular arc: the current point turns about the axis line through
`center` along `axis`, by `angle` radians (signed; positive turns
right-handed about the axis). Only the component of the start point
across the axis turns, so `center` names an axis *line* rather than a
point the arc must reach. The axis must have direction, the start point
must not lie on the axis, and the angle must not be zero.

### `helix`

```json
{"type": "helix", "radius": 14.0, "turns": 6.5, "height": {"param": "height"}}
```

A helix winding about the incoming tangent, starting exactly at the
current point: its axis is the line through the current point displaced
by `radius` against the frame's local X. It winds right-handed (local X
turning toward local Y), makes `turns` turns and rises `height` along
the tangent — so a fresh path's helix rises up +Z, which is a spring
standing on the origin. `radius` must be positive, and a helix that
makes zero turns and rises zero refuses to evaluate.

### `spline`

```json
{"type": "spline",
 "points": [[0.0, 90.0, -35.0], [60.0, 170.0, -10.0], [95.0, 215.0, -45.0]],
 "start_tangent": [0.0, 1.0, 0.0],
 "end_tangent": [0.0, 0.0, -1.0]}
```

A cubic spline through the points it runs toward — like every primitive
but a wrap, it begins where the path has reached, so `points` (at least
one) are what it runs through and toward, and the curve has one span
per declared point.

Interior tangents are Catmull-Rom (half the chord between the
neighbouring points), so the curve is C1 across every interior point by
construction. The optional `start_tangent` and `end_tangent` are
*directions* — their length is ignored — and leaving one out means what
no literal could state: leave the way you came (the incoming tangent),
arrive along the final chord. Consecutive points must not coincide, and
a spline whose velocity vanishes mid-span (a cusp) refuses to evaluate
rather than produce a NaN mesh.

### `wrap`

```json
{"type": "wrap",
 "around": [
   {"center": [0.0, 0.0], "radius": 8.0},
   {"center": [30.0, {"param": "idler"}], "radius": 3.0},
   {"center": [60.0, 0.0], "radius": 5.0}
 ],
 "teeth": {"pitch": 2.5, "height": 0.75, "flank": "trapezoid", "count": 6},
 "phase": {"param": "travel"}}
```

A belt: a closed planar loop around at least two ordered circles,
following their external tangents, clockwise seen from +Z. The circles
are declared in the world XY plane (`center` is `[x, y]`, each `radius`
positive), and consecutive circles must admit an external tangent — two
circles too close for one refuse to evaluate.

A wrap is the one primitive that declares where it is, so it must be
the **only** primitive in its path; and it is a closed loop by
construction, so its document must declare `"loop": true`. Its profile
travels with local X pointing outward and local Y along world +Z.

`teeth` is an optional trapezoidal tooth pattern displacing the
profile's inner face (the vertices at its minimum local X) toward the
circles:

- `pitch` — the nominal pitch of the belt standard, carried for the
  consumer; the actual period is the loop's length over `count`, which
  is what closes the pattern at the seam and keeps a moving idler
  changing the tooth pitch *length* rather than the tooth count.
- `height` — the tooth height (non-negative).
- `flank` — the flank shape; `"trapezoid"` is the v1 vocabulary.
- `count` — the tooth count, a positive **integer literal**, never a
  parameter: the count fixes topology.

Where the pattern sits is declared by at most one of:

- `anchor` — `{"span": k, "at": s}` pins the pattern's origin a
  distance `s` along tangent span `k` (spans are numbered from the
  circle they leave; a wrap around *k* circles has *k* of them). This
  is a belt clamped to a carriage: teeth stay meshed as the carriage
  runs.
- `phase` — belt travel from the wrap's own origin (where the belt
  leaves circle 0). This is a circulating belt: advance it each frame.

Declaring both is rejected — they name the same tooth-pattern origin.

## `loop`

`true` closes the path into a ring: the last ring of samples joins back
to the first, and there are no end caps. A `wrap` is a loop by
construction and its document must say so.

`loop: true` on a chain of other primitives is valid v1 vocabulary that
no build evaluates yet: both evaluators raise `NotImplementedError`
naming it (closing a general chain waits on an end frame that
rotation-minimizing transport does not bring back in general).

## `tessellation`

```json
{"path": 240, "profile": 16}
```

Both counts are positive integers, **declared and fixed** — they never
follow geometry or a parameter. That is the load-bearing rule of the
whole format: it makes the vertex count, ordering and triangulation a
function of the document alone, so two evaluations of one shape
correspond vertex for vertex ({doc}`concepts`).

- `profile` — vertices around the profile (for a polygon, exactly its
  point count).
- `path` — segments spent on **each element** of the path, not divided
  among them. A primitive's element count follows the document alone:
  one for a `line`, `arc` or `helix`; one span per declared point for a
  `spline`; two per circle (a span and an arc) for a `wrap`. A chain of
  *k* single-element primitives therefore has *k·path + 1* rings, and
  the ring at a joint is sampled once, by the primitive that leaves it.

## Validation

Validation is structural and needs no parameter values: it answers one
question — is this a v1 molejo document — and on the first offence
raises `SpecError` naming the offending element by its position
(`path[1].to[2]`, `tessellation.profile`). Both implementations
enforce the same rules with the same messages, held to it by shared
rejection fixtures.

What only values can reveal — an unbound parameter, a non-finite
binding, a line to nowhere, a wrap without an external tangent — is an
`EvaluationError` at evaluation time, again with identical messages in
both runtimes. Geometric sense is the author's obligation: the
representation does not police a self-intersecting sweep or an
over-compressed spring; the consumer's tests can.

## Versioning

`"molejo": 1` is the only version this implementation reads; any other
value is rejected naming the version it found and the version it reads.
A future spec version is a new integer, and a package version carries
the spec version it implements.
