# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Spec plus parameter values to a triangle mesh.

Evaluation is a sampling of the analytic sweep the spec defines, at the
resolution the spec declares. Because the counts are declared and never
adaptive, the *shape* of the output -- how many vertices, in what order,
joined by which triangles -- is a function of the document alone; the
parameter values move vertices and never renumber them. That is what
makes vertex correspondence free across bindings and parity with the
JavaScript twin in ``js/src/evaluate.js`` provable.

The conventions are pinned in design.md under "Sweep evaluation
conventions" and repeated here because the code must not be the only
place they live:

* The path starts at the origin with tangent ``+Z``; the profile lies in
  the plane perpendicular to the tangent with local axes ``+X`` and
  ``+Y``. Frame transport is rotation-minimizing, so a straight path
  carries a constant frame.
* Circle profile vertex *j* of *M* sits at angle ``2*pi*j/M``, at
  ``cos*x + sin*y`` in the profile frame.
* ``tessellation.path`` is a segment count *N* spent on *each element* of
  the path, and a primitive's element count follows the document alone
  (one for a line, arc or helix; one span per declared point for a
  spline; two per circle for a wrap). A chain of *k* single-element
  primitives has ``k*N + 1`` rings, and the ring at a joint is sampled
  once, by the primitive that leaves it. Wall vertex ``ring*M + j``; then
  the start-cap centre, then the end-cap centre.
* Faces run walls first (ring-major, then *j*, two triangles a quad),
  then the start-cap fan, then the end-cap fan. Winding is outward
  throughout: the start cap faces ``-tangent`` and the end cap
  ``+tangent``.
* A closed loop drops the duplicate ring and both caps: ring *R*-1's
  quads wrap onto ring 0, so ``V = R*M`` and ``F = 2*R*M``. Only a
  ``wrap`` path is a loop today; closing a general chain waits on the
  end frame, which transport does not bring back in general.

What this build evaluates is a circle or polygon profile swept along a
chain of ``line``, ``arc``, ``helix`` and ``spline`` primitives, or
around a ``wrap`` -- the whole v1 path vocabulary. What still raises
:class:`NotImplementedError` naming itself is ``loop: true`` on a chain
that is not a wrap, which waits on an end frame that transport does not
bring back in general.
"""

import math
import struct

import numpy as np

from .spec import _kind, _render, validate

__all__ = [
    "START_FRAME",
    "EvaluationError",
    "Frame",
    "Mesh",
    "evaluate",
    "minimal_rotation",
    "transport",
]

#: Below this the cross product of two unit vectors is noise, not an axis.
_PARALLEL = 1e-12


class EvaluationError(ValueError):
    """A spec cannot be evaluated at the given parameter values.

    The message names the offending element -- the parameter, the slot it
    is referenced from -- so a caller can bind what is missing. Structural
    faults are :class:`molejo.spec.SpecError`; this is what only values
    can reveal.
    """


# --- describing values in messages ----------------------------------------
#
# As in the validator, messages are byte-identical to the JavaScript
# evaluator's, so a value is described by its JSON kind and a non-finite
# number by a name both runtimes spell the same way.


def _describe(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _kind(value)
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "infinity" if value > 0 else "-infinity"
    return _render(value)


# --- parameter resolution --------------------------------------------------


def _resolve(slot, values, loc):
    """A numeric slot as a float, at the caller's parameter values."""
    if isinstance(slot, dict):
        name = slot["param"]
        if name not in values:
            raise EvaluationError(
                f"values: no value bound for parameter '{name}', referenced at {loc}"
            )
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvaluationError(
                f"values: parameter '{name}' must be a finite number, got "
                f"{_describe(value)} (referenced at {loc})"
            )
        if not math.isfinite(value):
            raise EvaluationError(
                f"values: parameter '{name}' must be a finite number, got "
                f"{_describe(value)} (referenced at {loc})"
            )
        return float(value)
    return float(slot)


def _resolve_vector(slots, values, loc):
    return np.array(
        [_resolve(slot, values, f"{loc}[{axis}]") for axis, slot in enumerate(slots)],
        dtype=np.float64,
    )


# --- frames ----------------------------------------------------------------
#
# A frame is a point on the path plus the orthonormal triple the profile is
# drawn in: `x` and `y` span the profile plane, `tangent` is the sweep
# direction, and (x, y, tangent) is right-handed so that walking the profile
# from vertex j to j+1 turns counter-clockwise seen from ahead -- which is
# what makes the winding below outward without a per-face normal check.


class Frame:
    """An oriented point on the path: ``origin`` plus ``x``, ``y``, ``tangent``."""

    __slots__ = ("origin", "x", "y", "tangent")

    def __init__(self, origin, x, y, tangent):
        self.origin = np.asarray(origin, dtype=np.float64)
        self.x = np.asarray(x, dtype=np.float64)
        self.y = np.asarray(y, dtype=np.float64)
        self.tangent = np.asarray(tangent, dtype=np.float64)

    def __repr__(self):
        return (
            f"Frame(origin={self.origin.tolist()}, x={self.x.tolist()}, "
            f"y={self.y.tolist()}, tangent={self.tangent.tolist()})"
        )


#: Where every path begins: the origin, looking up ``+Z``, with the profile
#: drawn in the world's ``+X``/``+Y``. Fixing this is what lets a document
#: describe a shape without also describing where it is: placement belongs
#: to the consumer.
START_FRAME = Frame(
    origin=(0.0, 0.0, 0.0), x=(1.0, 0.0, 0.0), y=(0.0, 1.0, 0.0), tangent=(0.0, 0.0, 1.0)
)


def _perpendicular(vector):
    """Some unit vector orthogonal to ``vector``, chosen deterministically."""
    axis = np.zeros(3)
    axis[int(np.argmin(np.abs(vector)))] = 1.0
    perpendicular = np.cross(vector, axis)
    return perpendicular / np.linalg.norm(perpendicular)


def _rodrigues(axis, angle):
    skew = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ]
    )
    return np.identity(3) + math.sin(angle) * skew + (1.0 - math.cos(angle)) * (skew @ skew)


def minimal_rotation(source, target):
    """The rotation taking unit ``source`` onto unit ``target`` and turning
    about nothing else -- the rotation-minimizing step of frame transport.

    Exactly the identity when the two directions are equal, which is what
    keeps the frame constant along a straight path. Antiparallel directions
    have no minimal rotation, so a deterministic perpendicular axis is
    chosen rather than an arbitrary one.
    """
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    axis = np.cross(source, target)
    sine = float(np.linalg.norm(axis))
    cosine = float(np.dot(source, target))
    if sine <= _PARALLEL:
        if cosine >= 0.0:
            return np.identity(3)
        return _rodrigues(_perpendicular(source), math.pi)
    return _rodrigues(axis / sine, math.atan2(sine, cosine))


def transport(frame, tangent, origin=None):
    """``frame`` carried onto a new tangent by the minimal rotation.

    The profile is not twisted about the tangent by the transport itself;
    any twist a primitive wants (a helix's, say) is that primitive's own
    business and is applied on top of this.
    """
    rotation = minimal_rotation(frame.tangent, tangent)
    return Frame(
        origin=frame.origin if origin is None else origin,
        x=rotation @ frame.x,
        y=rotation @ frame.y,
        tangent=np.asarray(tangent, dtype=np.float64),
    )


# --- profiles --------------------------------------------------------------


def _circle_points(profile, values, count):
    """Vertex *j* of *M* at angle ``2*pi*j/M``, at ``cos*x + sin*y``."""
    radius = _resolve(profile["radius"], values, "profile.radius")
    if radius <= 0.0:
        raise EvaluationError(
            f"profile.radius: must be a positive number, got {_describe(radius)}"
        )
    angles = 2.0 * np.pi * np.arange(count, dtype=np.float64) / count
    points = np.empty((count, 2), dtype=np.float64)
    points[:, 0] = radius * np.cos(angles)
    points[:, 1] = radius * np.sin(angles)
    return points


def _polygon_points(profile, values, count):
    """The declared points, in order; the count is theirs, checked already.

    A polygon's coordinates are ordinary numeric slots, so a profile may
    be driven by parameters like anything else. Their order is the
    author's: counter-clockwise in the profile frame, as the circle's is,
    or the sweep winds inward.
    """
    points = np.empty((count, 2), dtype=np.float64)
    for index, point in enumerate(profile["points"]):
        points[index] = _resolve_vector(point, values, f"profile.points[{index}]")
    return points


#: The profiles this build evaluates. One missing from here is valid v1
#: vocabulary that raises naming itself.
_PROFILES = {
    "circle": _circle_points,
    "polygon": _polygon_points,
}


def _profile_points(profile, values, count):
    """The profile as ``(count, 2)`` coordinates in the profile frame."""
    kind = profile["type"]
    sampler = _PROFILES.get(kind)
    if sampler is None:
        raise NotImplementedError(
            f"profile: the '{kind}' profile is not implemented yet; this molejo "
            f"build evaluates 'circle' and 'polygon' only"
        )
    return sampler(profile, values, count)


def _inner_face(points):
    """Which profile vertices the teeth displace: those at the minimum *x*.

    Exact equality, not a tolerance: a section whose inner face is flat
    -- every belt's is -- has two or more vertices there, and one whose
    inner face is rounded displaces a single vertex into a spike, which
    is authorship rather than something molejo guesses at.
    """
    return points[:, 0] == points[:, 0].min()


# --- paths -----------------------------------------------------------------


def _sample_path(path, values, segments):
    """The path as its ring centres ``(R, 3)`` and profile axes ``(R, 2, 3)``.

    ``tessellation.path`` is spent on every *element* of the path rather
    than divided among them: an arc-length-proportional split would make
    the ring count follow a parameter, which declared tessellation
    forbids. A primitive's element count is a function of the document
    alone -- one for a line, arc or helix, one per span for a spline of
    that many declared points, two per circle for a wrap -- so a chain of
    ``k`` single-element primitives is ``k * segments + 1`` rings.

    A primitive begins where its predecessor ended -- no primitive says
    where it starts -- so the ring at a joint is sampled once, by the
    primitive that leaves it, and the frame carried across is exactly the
    identity when the tangents agree.
    """
    frame = START_FRAME
    centres, axes = [], []
    for index, primitive in enumerate(path):
        loc = f"path[{index}]"
        primitive_centres, primitive_axes, frame = _SAMPLERS[primitive["type"]](
            primitive, values, segments, frame, loc
        )
        # The last ring of every primitive but the final one is the joint
        # ring, and belongs to the primitive that leaves it.
        keep = None if index == len(path) - 1 else -1
        centres.append(primitive_centres[:keep])
        axes.append(primitive_axes[:keep])
    return np.concatenate(centres), np.concatenate(axes)


def _held(frame, segments):
    """The profile axes of a primitive whose frame does not turn."""
    axes = np.empty((segments + 1, 2, 3), dtype=np.float64)
    axes[:, 0, :] = frame.x
    axes[:, 1, :] = frame.y
    return axes


def _carried(frame, centres, tangents):
    """The profile axes along a turning primitive, ring by ring.

    Transport is composed step by step rather than taken in one jump from
    the incoming frame: that is the discrete rotation-minimizing frame,
    and it is what a curve turning under the profile means. For an arc the
    two agree exactly -- every tangent lies in the plane perpendicular to
    the arc's axis, so every step turns about that same axis -- and for a
    helix, whose tangents trace a cone, only the composition is
    rotation-minimizing.
    """
    axes = np.empty((len(centres), 2, 3), dtype=np.float64)
    for ring, tangent in enumerate(tangents):
        frame = transport(frame, tangent, centres[ring])
        axes[ring, 0, :] = frame.x
        axes[ring, 1, :] = frame.y
    return axes, frame


def _sample_line(primitive, values, segments, frame, loc):
    """A straight run from the frame's origin to ``to``.

    The frame is transported once, at the segment's start, and then held:
    a line has one tangent, so a rotation-minimizing transport along it is
    the identity.
    """
    start = frame.origin
    end = _resolve_vector(primitive["to"], values, f"{loc}.to")
    direction = end - start
    length = float(np.linalg.norm(direction))
    if length <= 0.0:
        raise EvaluationError(
            f"{loc}.to: a line must go somewhere; its end coincides with its start"
        )
    frame = transport(frame, direction / length, end)

    steps = np.arange(segments + 1, dtype=np.float64) / segments
    centres = start + steps[:, None] * direction
    return centres, _held(frame, segments), frame


def _arc_geometry(primitive, values, frame, loc):
    """The circle an ``arc`` runs on, and the three ways it can be degenerate.

    Only the component of ``start - center`` across the axis turns, so
    ``center`` names an axis line rather than a point the arc must reach:
    what comes back is the centre *on* that line, the radius, and the
    radial and tangential units the turn is measured in. The B-rep
    evaluator builds its edge from the same numbers, so the refusals and
    their wording are paid for once.
    """
    center = _resolve_vector(primitive["center"], values, f"{loc}.center")
    axis = _resolve_vector(primitive["axis"], values, f"{loc}.axis")
    angle = _resolve(primitive["angle"], values, f"{loc}.angle")

    length = float(np.linalg.norm(axis))
    if length <= 0.0:
        raise EvaluationError(
            f"{loc}.axis: an arc needs an axis to turn about; its axis has no direction"
        )
    axis = axis / length

    spoke = frame.origin - center
    axial = float(np.dot(spoke, axis)) * axis
    spoke = spoke - axial
    radius = float(np.linalg.norm(spoke))
    if radius <= 0.0:
        raise EvaluationError(
            f"{loc}.center: an arc needs a radius to turn on; its start point lies "
            f"on its axis"
        )
    if angle == 0.0:
        raise EvaluationError(
            f"{loc}.angle: an arc must turn somewhere; its angle is 0"
        )

    radial = spoke / radius
    return {
        "centre": center + axial,
        "axis": axis,
        "angle": angle,
        "radius": radius,
        "radial": radial,
        "tangential": np.cross(axis, radial),
    }


def _sample_arc(primitive, values, segments, frame, loc):
    """The current point turned about the axis line through ``center``.

    Ring *i* of *N* sits at ``phi = i*angle/N`` on the circle
    :func:`_arc_geometry` names, and the tangent is the circle's, signed
    by the direction of the turn.
    """
    arc = _arc_geometry(primitive, values, frame, loc)
    radius, radial, tangential = arc["radius"], arc["radial"], arc["tangential"]
    angle = arc["angle"]

    turn = angle * np.arange(segments + 1, dtype=np.float64) / segments
    cosine = np.cos(turn)[:, None]
    sine = np.sin(turn)[:, None]

    centres = arc["centre"] + radius * (cosine * radial + sine * tangential)
    sign = 1.0 if angle > 0.0 else -1.0
    tangents = sign * (cosine * tangential - sine * radial)
    axes, frame = _carried(frame, centres, tangents)
    return centres, axes, frame


def _helix_geometry(primitive, values, frame, loc):
    """The cylinder a ``helix`` winds on, and the two ways it can degenerate.

    Its axis is the line through ``origin - radius * x`` along the
    tangent, so the helix starts exactly where the path is; it winds
    right-handed (the frame's *x* turning toward its *y*) and advances
    ``height`` over ``turns`` turns. ``speed`` is constant -- it is the
    helix's length -- so rings uniform in the turn parameter are uniform
    in arc length. The B-rep evaluator makes its curve on exactly this
    cylinder, so the refusals live here rather than in either sampler.
    """
    radius = _resolve(primitive["radius"], values, f"{loc}.radius")
    turns = _resolve(primitive["turns"], values, f"{loc}.turns")
    height = _resolve(primitive["height"], values, f"{loc}.height")

    if radius <= 0.0:
        raise EvaluationError(
            f"{loc}.radius: must be a positive number, got {_describe(radius)}"
        )
    around = 2.0 * math.pi * turns * radius
    speed = math.hypot(around, height)
    if speed <= 0.0:
        raise EvaluationError(
            f"{loc}: a helix must go somewhere; it makes 0 turns and rises 0"
        )

    return {
        "radius": radius,
        "turns": turns,
        "height": height,
        "around": around,
        "speed": speed,
        "axis_point": frame.origin - radius * frame.x,
    }


def _sample_helix(primitive, values, segments, frame, loc):
    """A helix winding about the incoming tangent, from the current point.

    Ring *i* of *N* sits at ``u = i/N`` on the cylinder
    :func:`_helix_geometry` names, at turn ``2*pi*turns*u`` and rise
    ``height*u``.
    """
    helix = _helix_geometry(primitive, values, frame, loc)
    radius, turns = helix["radius"], helix["turns"]
    height, around, speed = helix["height"], helix["around"], helix["speed"]

    axis_point = helix["axis_point"]
    steps = np.arange(segments + 1, dtype=np.float64) / segments
    turn = 2.0 * math.pi * turns * steps
    cosine = np.cos(turn)[:, None]
    sine = np.sin(turn)[:, None]

    centres = (
        axis_point
        + radius * (cosine * frame.x + sine * frame.y)
        + (height * steps)[:, None] * frame.tangent
    )
    tangents = (
        around * (-sine * frame.x + cosine * frame.y) + height * frame.tangent
    ) / speed
    axes, frame = _carried(frame, centres, tangents)
    return centres, axes, frame


def _spline_direction(declared, fallback, loc, what):
    """A declared end tangent as a unit direction, or the fallback.

    What the author declares is where the curve points; the length is
    ignored, exactly as an arc's axis is, because the Hermite speed at an
    end comes from the adjacent chord -- the same scale the Catmull-Rom
    interior tangents carry.
    """
    if declared is None:
        return fallback
    length = float(np.linalg.norm(declared))
    if length <= 0.0:
        raise EvaluationError(
            f"{loc}: a spline's {what} tangent needs a direction; it has no length"
        )
    return declared / length


def _spline_tangents(primitive, values, frame, loc):
    """The points a spline runs through and the tangent it carries at each.

    The spline begins where the path has reached, so ``points`` are what
    it runs through and toward: with that start *P0* and the declared
    *P1 … Pn* it has *n* spans.

    The tangent at each point is Catmull-Rom inside
    (``m_i = (P_{i+1} - P_{i-1})/2``) and declared at the two ends, scaled
    to the adjacent chord. An absent ``start_tangent`` means the incoming
    tangent -- so a lead-in hands over without a kink -- and an absent
    ``end_tangent`` means the final chord. Neither default is a value the
    document could have written, because both follow parameter values.

    Consecutive spans share the tangent vector at the point between them,
    so the curve is C1 across every interior point by construction rather
    than by the author's care -- which is also what lets the B-rep
    evaluator write the whole chain as one cubic B-spline from these very
    numbers.
    """
    points = np.empty((len(primitive["points"]) + 1, 3), dtype=np.float64)
    points[0] = frame.origin
    for index, point in enumerate(primitive["points"]):
        points[index + 1] = _resolve_vector(point, values, f"{loc}.points[{index}]")
    spans = len(points) - 1

    declared_start = (
        _resolve_vector(primitive["start_tangent"], values, f"{loc}.start_tangent")
        if "start_tangent" in primitive
        else None
    )
    declared_end = (
        _resolve_vector(primitive["end_tangent"], values, f"{loc}.end_tangent")
        if "end_tangent" in primitive
        else None
    )

    chords = np.linalg.norm(np.diff(points, axis=0), axis=1)
    for index, chord in enumerate(chords):
        if chord <= 0.0:
            raise EvaluationError(
                f"{loc}.points[{index}]: a spline must go somewhere; points[{index}] "
                f"coincides with the point before it"
            )

    tangents_at = np.empty_like(points)
    tangents_at[0] = chords[0] * _spline_direction(
        declared_start, frame.tangent, f"{loc}.start_tangent", "start"
    )
    for index in range(1, spans):
        tangents_at[index] = 0.5 * (points[index + 1] - points[index - 1])
        if float(np.linalg.norm(tangents_at[index])) <= 0.0:
            raise EvaluationError(
                f"{loc}.points[{index - 1}]: a spline needs a direction where it "
                f"turns; the points on either side of points[{index - 1}] coincide"
            )
    tangents_at[spans] = (
        points[spans] - points[spans - 1]
        if declared_end is None
        else chords[spans - 1]
        * _spline_direction(declared_end, None, f"{loc}.end_tangent", "end")
    )
    return points, tangents_at


def _sample_spline(primitive, values, segments, frame, loc):
    """The Hermite chain :func:`_spline_tangents` describes, sampled.

    Each of the *n* spans is spent ``segments`` segments and the ring at a
    joint belongs to the span that leaves it, so a lone spline is
    ``n*segments + 1`` rings.
    """
    points, tangents_at = _spline_tangents(primitive, values, frame, loc)
    spans = len(points) - 1

    centres = np.empty((spans * segments + 1, 3), dtype=np.float64)
    tangents = np.empty_like(centres)
    at = 0
    for index in range(spans):
        # The last span alone contributes its final ring: a joint's ring
        # belongs to the span that leaves it.
        rings = segments + 1 if index == spans - 1 else segments
        step = np.arange(rings, dtype=np.float64) / segments
        square = step * step
        cube = square * step
        here, there = points[index], points[index + 1]
        leaving, arriving = tangents_at[index], tangents_at[index + 1]

        # The Hermite basis is exactly (1, 0, 0, 0) at t = 0 and exactly
        # (0, 0, 1, 0) at t = 1, so every declared point is hit bit for bit.
        centres[at : at + rings] = (
            (2.0 * cube - 3.0 * square + 1.0)[:, None] * here
            + (cube - 2.0 * square + step)[:, None] * leaving
            + (3.0 * square - 2.0 * cube)[:, None] * there
            + (cube - square)[:, None] * arriving
        )
        velocity = (
            (6.0 * square - 6.0 * step)[:, None] * (here - there)
            + (3.0 * square - 4.0 * step + 1.0)[:, None] * leaving
            + (3.0 * square - 2.0 * step)[:, None] * arriving
        )
        speed = np.linalg.norm(velocity, axis=1)
        if not speed.all():
            # A cusp the author asked for. Refused rather than divided by,
            # because a NaN mesh is not the deterministic and visibly wrong
            # a kinked joint is.
            raise EvaluationError(
                f"{loc}: a spline must be going somewhere at every ring; its tangent "
                f"vanishes on the span to points[{index}]"
            )
        tangents[at : at + rings] = velocity / speed[:, None]
        at += rings

    axes, frame = _carried(frame, centres, tangents)
    return centres, axes, frame


def _wrap_circles(primitive, values, loc):
    """The circles a belt runs outside, and the normal it touches each on.

    A wrap is planar -- it lies in the world XY plane, because its
    circles are declared there -- and it runs the external tangents,
    clockwise seen from ``+Z``, touching every circle along its outward
    normal. For consecutive circles at distance *L* with radii *r* and
    *r'*, the shared outward normal is

        n = delta*chat + sqrt(1 - delta^2)*rot90(chat),  delta = (r - r')/L

    and the direction of travel is ``(n_y, -n_x)``. Both refusals a wrap
    can meet through parameter values live here, so the mesh and the
    B-rep say the same words.
    """
    circles = primitive["around"]
    count = len(circles)

    centres, radii = [], []
    for index, circle in enumerate(circles):
        centres.append(
            _resolve_vector(circle["center"], values, f"{loc}.around[{index}].center")
        )
        radius = _resolve(circle["radius"], values, f"{loc}.around[{index}].radius")
        if radius <= 0.0:
            raise EvaluationError(
                f"{loc}.around[{index}].radius: must be a positive number, got "
                f"{_describe(radius)}"
            )
        radii.append(radius)

    normals = []
    for index in range(count):
        following = (index + 1) % count
        span = centres[following] - centres[index]
        length = float(np.linalg.norm(span))
        gap = radii[index] - radii[following]
        if length <= abs(gap):
            raise EvaluationError(
                f"{loc}.around[{following}]: a wrap needs an external tangent between "
                f"consecutive circles; around[{index}] and around[{following}] are too "
                f"close for one"
            )
        direction = span / length
        delta = gap / length
        across = np.array([-direction[1], direction[0]])
        normals.append(delta * direction + math.sqrt(1.0 - delta * delta) * across)

    return centres, radii, normals


def _wrap_elements(centres, radii, normals):
    """The 2k elements of the loop, each with the station it starts at.

    Span 0, the arc about circle 1, span 1, … and finally the arc about
    circle 0, so the loop's own origin is where the belt leaves circle 0.
    A span is a straight run between two tangent points; an arc runs
    clockwise about a circle from the normal the belt arrives on to the
    one it leaves on. Nothing here is sampled: this is the exact
    decomposition the B-rep evaluator turns into line and arc edges, and
    the one the mesh evaluator then spends its segments on.
    """
    count = len(radii)
    elements = []
    travelled = 0.0
    for index in range(count):
        following = (index + 1) % count
        normal = normals[index]

        start = centres[index] + radii[index] * normal
        end = centres[following] + radii[following] * normal
        length = float(np.linalg.norm(end - start))
        elements.append(
            {
                "kind": "span",
                "start": start,
                "end": end,
                "normal": normal,
                "station": travelled,
                "length": length,
            }
        )
        travelled += length

        arrival = math.atan2(normal[1], normal[0])
        departure = math.atan2(normals[following][1], normals[following][0])
        turn = (arrival - departure) % (2.0 * math.pi)
        radius = radii[following]
        elements.append(
            {
                "kind": "arc",
                "centre": centres[following],
                "radius": radius,
                "from": arrival,
                "turn": turn,
                "station": travelled,
                "length": radius * turn,
            }
        )
        travelled += radius * turn

    return elements, travelled


def _wrap_geometry(primitive, values, segments, loc):
    """The belt's ring centres, tangents, and arc-length stations.

    Each of the ``2k`` elements is spent ``segments`` rings, uniformly in
    arc length -- uniformly in angle on an arc -- and a joint's ring
    belongs to the element that leaves it, as in any chain.
    """
    centres, radii, normals = _wrap_circles(primitive, values, loc)
    elements, travelled = _wrap_elements(centres, radii, normals)
    count = len(radii)

    rings = 2 * count * segments
    ring_centres = np.zeros((rings, 3), dtype=np.float64)
    tangents = np.zeros((rings, 3), dtype=np.float64)
    stations = np.empty(rings, dtype=np.float64)
    steps = np.arange(segments, dtype=np.float64) / segments

    at = 0
    for element in elements:
        station, length = element["station"], element["length"]
        if element["kind"] == "span":
            start, end = element["start"], element["end"]
            normal = element["normal"]
            ring_centres[at : at + segments, :2] = start + steps[:, None] * (end - start)
            tangents[at : at + segments, 0] = normal[1]
            tangents[at : at + segments, 1] = -normal[0]
        else:
            centre, radius = element["centre"], element["radius"]
            angles = element["from"] - element["turn"] * steps
            cosine = np.cos(angles)
            sine = np.sin(angles)
            ring_centres[at : at + segments, 0] = centre[0] + radius * cosine
            ring_centres[at : at + segments, 1] = centre[1] + radius * sine
            tangents[at : at + segments, 0] = sine
            tangents[at : at + segments, 1] = -cosine
        stations[at : at + segments] = station + steps * length
        at += segments

    return {
        "centres": ring_centres,
        "tangents": tangents,
        "stations": stations,
        "length": travelled,
        "elements": elements,
    }


def _sample_wrap(primitive, values, segments, frame, loc):
    """A belt around ordered circles, as a closed planar loop.

    The one primitive that says where it is, so it starts in a frame of
    its own rather than the one it is handed -- which is why validation
    keeps it alone in its path. Local *x* is the outward normal and local
    *y* is world ``+Z``, and the belt circulates clockwise seen from
    ``+Z`` so that triple is right-handed and the pinned outward winding
    needs no special case. Transport is then the ordinary ring-by-ring
    one: the path is planar, so every minimal rotation is about ``+/-Z``
    and the frame comes back to the start frame at the seam.
    """
    wrap = _wrap_geometry(primitive, values, segments, loc)
    centres, tangents = wrap["centres"], wrap["tangents"]
    start = Frame(
        origin=centres[0],
        x=(-tangents[0][1], tangents[0][0], 0.0),
        y=(0.0, 0.0, 1.0),
        tangent=tangents[0],
    )
    axes, frame = _carried(start, centres, tangents)
    return centres, axes, frame


def _modulation(stations, origin, period):
    """The tooth trapezoid at the given arc-length stations.

    One period is a quarter crest centred on the pattern origin, a
    quarter ramp, a quarter root and a quarter ramp back. The origin is a
    crest centre, which is what makes an anchor mean "a tooth is clamped
    here".
    """
    fraction = ((stations - origin) / period) % 1.0
    distance = np.minimum(fraction, 1.0 - fraction)
    return np.clip((0.375 - distance) * 4.0, 0.0, 1.0)


def _wrap_pattern(primitive, values, elements, length, loc):
    """Where the tooth pattern sits, how long its period is, and how tall.

    The period is the loop's length over the declared count: an integer
    count over the whole loop is what closes the pattern at the seam, and
    what keeps a moving idler changing the tooth pitch *length* rather
    than the tooth count. The declared ``teeth.pitch`` is the nominal
    pitch of the belt standard and is not read here (see design.md, "The
    wrap").

    The origin is ``anchor`` (a distance along a named tangent span, so a
    belt clamped to a carriage keeps its teeth meshed as the carriage
    runs), or ``phase`` (belt travel from the wrap's own origin), or the
    wrap's own origin when the document names neither. It is resolved
    even for a wrap without teeth, so a dangling reference in it is still
    an error rather than a slot nobody read.
    """
    teeth = primitive.get("teeth")
    anchor = primitive.get("anchor")

    origin = 0.0
    if anchor is not None:
        origin = elements[2 * anchor["span"]]["station"] + _resolve(
            anchor["at"], values, f"{loc}.anchor.at"
        )
    elif "phase" in primitive:
        origin = _resolve(primitive["phase"], values, f"{loc}.phase")

    if teeth is None:
        return None
    height = _resolve(teeth["height"], values, f"{loc}.teeth.height")
    if height < 0.0:
        raise EvaluationError(
            f"{loc}.teeth.height: must be a non-negative number, got "
            f"{_describe(height)}"
        )
    return origin, length / teeth["count"], height


def _wrap_displacement(primitive, values, segments, loc):
    """How far each ring's inner face is pushed toward the circles."""
    if (
        primitive.get("teeth") is None
        and primitive.get("anchor") is None
        and "phase" not in primitive
    ):
        return None

    wrap = _wrap_geometry(primitive, values, segments, loc)
    pattern = _wrap_pattern(
        primitive, values, wrap["elements"], wrap["length"], loc
    )
    if pattern is None:
        return None
    origin, period, height = pattern
    return height * _modulation(wrap["stations"], origin, period)


#: The whole v1 path vocabulary, each primitive with its sampler. There is
#: no fallback here because there is nothing left to fall back from:
#: validation refuses a primitive this table does not name.
_SAMPLERS = {
    "line": _sample_line,
    "arc": _sample_arc,
    "helix": _sample_helix,
    "spline": _sample_spline,
    "wrap": _sample_wrap,
}


# --- mesh assembly ---------------------------------------------------------


def _wall_vertices(centres, axes, points, inner=None, displacement=None):
    """Ring-major wall vertices: ``ring*M + j``, in the ring's own frame.

    ``displacement`` is a per-ring offset pushing the profile's inner
    face -- the vertices ``inner`` marks -- toward the negative local
    *x*; that is what a tooth is. Without it the profile is the same at
    every ring, which is every primitive but a toothed wrap.
    """
    u = np.broadcast_to(points[:, 0], (len(centres), len(points)))
    v = points[:, 1]
    if displacement is not None:
        u = u - displacement[:, None] * inner[None, :]
    return (
        centres[:, None, :]
        + u[:, :, None] * axes[:, None, 0, :]
        + v[None, :, None] * axes[:, None, 1, :]
    )


def _faces(rings, count, loop=False):
    """Walls (ring-major), then the start-cap fan, then the end-cap fan.

    A loop has neither cap and one more band of walls: its last ring's
    quads wrap onto ring 0, which is what closes the belt without a
    duplicate ring.
    """
    j = np.arange(count, dtype=np.int64)
    following = (j + 1) % count
    bands = rings if loop else rings - 1
    ring = np.arange(bands, dtype=np.int64)[:, None] * count
    onward = ((np.arange(bands, dtype=np.int64) + 1) % rings)[:, None] * count

    a = ring + j[None, :]
    b = ring + following[None, :]
    c = onward + following[None, :]
    d = onward + j[None, :]
    quads = np.empty((bands, count, 2, 3), dtype=np.int32)
    quads[:, :, 0, 0] = a
    quads[:, :, 0, 1] = b
    quads[:, :, 0, 2] = c
    quads[:, :, 1, 0] = a
    quads[:, :, 1, 1] = c
    quads[:, :, 1, 2] = d

    if loop:
        # No open end, so nothing to cap: the walls already close.
        return quads.reshape(-1, 3)

    start_centre = rings * count
    end_centre = start_centre + 1
    last = (rings - 1) * count

    # The start cap winds backwards around ring 0, so it faces -tangent;
    # the end cap winds forwards around the last ring, facing +tangent.
    start_cap = np.empty((count, 3), dtype=np.int32)
    start_cap[:, 0] = start_centre
    start_cap[:, 1] = following
    start_cap[:, 2] = j

    end_cap = np.empty((count, 3), dtype=np.int32)
    end_cap[:, 0] = end_centre
    end_cap[:, 1] = last + j
    end_cap[:, 2] = last + following

    return np.concatenate(
        [quads.reshape(-1, 3), start_cap, end_cap], axis=0, dtype=np.int32
    )


class Mesh:
    """A triangle mesh: float64 vertices ``(V, 3)``, int32 faces ``(F, 3)``.

    Watertight by construction -- a closed profile swept and capped admits
    no hole -- and deterministic: one document and one binding always give
    the identical bytes.
    """

    __slots__ = ("vertices", "faces")

    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces

    def __repr__(self):
        return f"Mesh({len(self.vertices)} vertices, {len(self.faces)} faces)"

    # -- export -------------------------------------------------------------

    #: 80 bytes that deliberately do not begin with "solid", which readers
    #: take as the mark of an ASCII STL.
    STL_HEADER = b"molejo binary STL - analytic flexible parts for mechanical CAD"

    def to_stl(self):
        """The mesh as binary STL bytes: header, count, 50 bytes a facet."""
        triangles = self.vertices[self.faces]
        normals = np.cross(
            triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
        )
        lengths = np.linalg.norm(normals, axis=1)
        # A degenerate facet gets a zero normal rather than a division by zero;
        # readers recompute normals from the winding anyway.
        np.divide(normals, lengths[:, None], out=normals, where=lengths[:, None] > 0.0)

        facet = np.dtype(
            [("normal", "<f4", (3,)), ("corners", "<f4", (3, 3)), ("attribute", "<u2")]
        )
        assert facet.itemsize == 50, "a binary STL facet is 50 bytes"
        facets = np.zeros(len(self.faces), dtype=facet)
        facets["normal"] = normals
        facets["corners"] = triangles

        header = self.STL_HEADER.ljust(80, b"\0")[:80]
        return header + struct.pack("<I", len(self.faces)) + facets.tobytes()


# --- the evaluation --------------------------------------------------------


def _looped(document):
    """Whether this path closes -- refusing the loop no build closes yet.

    A wrap is a closed loop and validation has already made its document
    say so; closing a chain of other primitives waits on the end frame,
    which a rotation-minimizing transport does not bring back in general.
    Both evaluators ask here, so neither can quietly close what the other
    refuses.
    """
    looped = document["path"][0]["type"] == "wrap"
    if document.get("loop", False) and not looped:
        raise NotImplementedError(
            "loop: closing a chain of primitives is not implemented yet; this "
            "molejo build closes the loop of a 'wrap' path only"
        )
    return looped


def evaluate(document, values=None):
    """Evaluate a molejo document at the given parameter values.

    ``values`` is a plain ``{name: number}`` mapping; names the document
    does not reference are ignored, so a consumer may hand over its whole
    machine state. A name the document *does* reference and the mapping
    does not bind is an error naming both the parameter and the slot: no
    partial or repaired mesh is ever returned.
    """
    validate(document)
    values = {} if values is None else values

    path = document["path"]
    looped = _looped(document)

    count = document["tessellation"]["profile"]
    segments = document["tessellation"]["path"]

    # Everything a parameter can touch is resolved before a single vertex is
    # written, which is what makes "no partial output" true rather than hoped.
    points = _profile_points(document["profile"], values, count)
    centres, axes = _sample_path(path, values, segments)
    displacement = (
        _wrap_displacement(path[0], values, segments, "path[0]") if looped else None
    )

    rings = len(centres)
    walls = _wall_vertices(
        centres, axes, points, _inner_face(points), displacement
    ).reshape(-1, 3)
    if looped:
        return Mesh(vertices=np.ascontiguousarray(walls), faces=_faces(rings, count, True))

    vertices = np.empty((rings * count + 2, 3), dtype=np.float64)
    vertices[: rings * count] = walls
    vertices[rings * count] = centres[0]
    vertices[rings * count + 1] = centres[-1]

    return Mesh(vertices=vertices, faces=_faces(rings, count))
