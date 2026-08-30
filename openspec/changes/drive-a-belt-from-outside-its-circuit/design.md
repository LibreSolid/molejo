# Design

## One formula, with signed radii

The v1 wrap rule already generalizes. For consecutive circles at
distance *L* with radii *r* and *r'*, the shared outward normal is

    n = d·û + √(1 − d²)·rot90(û),   d = (r − r')/L

the belt touches each circle at `centre + r·n`, and travel runs along
`(n_y, −n_x)`. Sign each radius by which way the belt turns about its
circle — `+r` clockwise, `−r` counterclockwise — and the same three
lines produce the external tangent where the two senses agree and the
internal tangent where they differ. Nothing branches: the only change is
that `r` may be negative in three places (the normal, the two touch
points) and that the existence condition `L > |r − r'|` now reads as
`L > r + r'` across a reverse bend, which is exactly the internal
tangent's condition.

This matters more than tidiness. The rule is restated in four places —
both mesh evaluators, the OCCT evaluator, and each suite's independent
closed form — and a version of it that branched on sense would be four
opportunities to branch differently.

## An arc is named by the point, not by the normal

A v1 arc records the *normal* the belt arrives on, because on a circle
wrapped from outside the arrival point is a radius along that normal.
Across a reverse bend it is a radius *against* it: the two differ by half
a turn. So an arc records the angle of the point, `atan2(s·n)`, and its
turn is `s·(arrival − departure) mod 2π`, sampled as
`arrival − s·turn·t`. That reduces exactly to v1 when `s = +1`, which is
what keeps every existing fixture byte-identical.

## The tooth face is a consequence, not a second decision

The profile frame's local *x* is the left normal of travel throughout,
carried ring to ring by rotation-minimizing transport. On a clockwise arc
that points away from the circle; on a counterclockwise one the tangent
has swung half a turn and it points *at* the circle. So the belt's two
faces swap which one meets the metal exactly where the sense changes —
which is the geometry doing the work, not a special case.

What remains genuinely undecidable from the geometry is which face of the
*belt* carries the teeth, because that is a fact about the part rather
than about the loop: a belt has teeth on one side and it is the machine
that decides which side faces in. Hence `face`, and hence its default
being `inner` — the only face v1 could displace.

`face` is a property of `teeth` rather than of the profile because it
answers "which of these vertices move", and nothing else in the document
moves vertices. Putting it on the profile would give a section a tooth
face even in a document with no teeth at all.

## Why the version integer is enforced both ways

molejo's compatibility handle is `"molejo": n`, and 0.1.0 is published
with n = 1. Two failure modes follow, and both are cheap to close.

A document that **understates** itself — declares 1 and uses `turn` —
would reach a v1 implementation as `unknown field 'turn'`, which reads as
a malformed document rather than as one written for a newer molejo. So
validation computes the lowest version a document's vocabulary needs and
rejects a declaration below it, naming the field that forced it.

A document that **overstates** itself is the subtler and more damaging
one. If the authoring layer simply wrote `SPEC_VERSION`, then every
existing shape — a spring, a cylinder, the X-axis belt — would start
emitting `"molejo": 2` and become unreadable by molejo 0.1.0 in the
wild, for no reason at all. So an author writes the *lowest* version its
document needs. A shape that asks nothing of v2 emits the v1 document it
always did, byte for byte; only a document that genuinely cannot be
evaluated by 0.1.0 is marked as one it cannot read.

That also keeps the whole existing fixture set unchanged, which is
itself evidence: if v2 had altered a single vertex of a v1 document, the
parity suites would say so.

## What the new fixture has to be able to fail

The parity fixture puts the two additions together and binds the
reverse-bent circle's centre to a parameter, because a moving reverse-bent
circle changes the internal tangents on *both* sides of it and the loop
length with them. An evaluator that took the external tangent, turned the
arc the ordinary way, or displaced the inner face departs on the first
vertex of the first case.

Its tooth count is chosen against its sampling — six teeth over 72 rings,
twelve rings a tooth, matching the existing belt fixtures. That is not
cosmetic: the B-rep parity suite asserts the exact solid is the larger of
the two, and on an *outward*-toothed trace the chords cut a crest off
(area down) and cut a root corner (area up) in opposition, so a fixture
sampled at three rings a tooth aliases its own teeth and can come out
larger than the solid it samples. Twelve rings a tooth leaves the
faceting deficit where it belongs.
