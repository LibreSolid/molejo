## Why

A v1 `wrap` can only draw a belt driven from *inside* its own circuit.
It runs the external tangents of every circle, so the loop is convex
everywhere; and its teeth displace the profile's inner face, so they
point at whatever the loop encloses. That is the right shape for a belt
whose drive pulley is one of the circles it wraps — the Metamaquina 2 X
axis, and the two belt fixtures already in the repository.

It is not the shape a great many real machines use. When the drive
pulley is small and the belt has to be forced onto it, the machine puts
two idlers either side of the pulley and threads the belt *between* them
and *over* it: the belt leaves the first idler on an internal tangent,
hugs the pulley from the far side, and crosses back out to the second.
The loop is concave there and convex everywhere else. Because the belt
turns the other way about that one circle, the profile frame turns with
it, and the face that meets the pulley is the *outer* one — so the teeth
must stand there, and the smooth back is what rides the bare idler
races, which is what a bare race is for.

The originating finding is the Metamaquina 2 Y axis. Its design draws
the loop on three bare 608 bearings, and drawn that way the belt passes
22 mm clear of the motor pulley: an axis with no drive at all. What the
machine really does is the reverse bend above — the two rear bearings
stand 58 mm apart with the motor 40 mm inside the line between them, and
the belt wraps 156° of the pulley. Neither half of that could be
expressed in v1, so the consumer could not draw its own machine.

Both halves are one thing, and neither is useful alone: a reverse bend
with inward teeth presents the belt's smooth back to the pulley, and
outward teeth on a convex loop are teeth facing nothing.

## What Changes

Spec version 2, which only *adds* vocabulary:

- **spec-schema**: a `wrap` circle takes an optional `turn`
  (`clockwise`, the default, or `counterclockwise`); a wrap's `teeth`
  takes an optional `face` (`inner`, the default, or `outer`). Both are
  literals, never parameters: each decides which elements the loop has
  or which vertices move, and neither may follow a value. The version
  integer becomes a two-way promise: a document may not use vocabulary
  the version it declares cannot express, and an author writes the
  lowest version a document needs so that nothing overstates itself
  either.
- **python-evaluator**, **js-evaluator**, **brep-evaluator**: one
  signed-radius formula replaces the external-tangent one, so a tangent
  is external where two circles' senses agree and internal where they
  differ; arcs turn the way their circle's sense says and carry the
  profile frame with them; the tooth displacement runs toward or away
  from the circles according to `face`.
- **parity**: one new fixture exercising both additions together, and
  three new rejection fixtures.
- **distribution**: both packages go to `0.2.0`, carrying spec version 2.

## Capabilities

### New Capabilities

None. Every capability already exists; this change extends five of them
and adds a fixture to the sixth.

### Modified Capabilities

`spec-schema`, `python-evaluator`, `js-evaluator`, `brep-evaluator`,
`parity`, `distribution`.

## Impact

- `python/molejo/spec.py` — `turn`, `face`, the version vocabulary gate,
  and `required_version`.
- `python/molejo/evaluator.py` — signed radii, sensed arcs, the signed
  tooth displacement.
- `python/molejo/_occt.py` — the same three, in edges and traces.
- `python/molejo/authoring.py` — `Teeth(face=…)`, and writing the lowest
  version a document needs.
- `js/src/spec.js`, `js/src/evaluate.js` — the twin of all of it.
- `fixtures/reverse-bend-belt.json` and the manifest;
  `fixtures/invalid/unknown-wrap-turn.json`,
  `fixtures/invalid/unknown-tooth-face.json`,
  `fixtures/invalid/understated-version.json`.
- `docs/spec.md`, `docs/python.md`, `docs/brep.md`, `docs/quickstart.md`,
  `README.md`, `CHANGELOG.md`, `fixtures/README.md`.
- Consumer validation (the empirical origin, recorded here, exercised
  outside this repository): the Metamaquina 2 Y axis, whose belt now
  wraps 156° of its motor pulley and turns it exactly one groove per
  tooth of bed travel.

## Out of scope

- Any way to make a circle's sense follow a parameter. A sense decides
  which tangents the loop takes and therefore which elements it has;
  letting it move would make the element count follow a value, which
  declared tessellation forbids for the same reason the tooth count is a
  literal.
- Teeth on both faces, or a tooth form other than the trapezoid.
- Policing a reverse bend whose offsets exceed the radius of curvature,
  or a loop whose spans cross. Geometric sense remains the author's
  obligation, as it is for every other primitive; the consumer's tests
  can check it and this one's do.
