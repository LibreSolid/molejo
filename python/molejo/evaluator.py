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
* ``tessellation.path`` is a segment count *N* spent on *each* path
  primitive: a chain of *k* primitives has ``k*N + 1`` rings, and the
  ring at a joint is sampled once, by the primitive that leaves it. Wall
  vertex ``ring*M + j``; then the start-cap centre, then the end-cap
  centre.
* Faces run walls first (ring-major, then *j*, two triangles a quad),
  then the start-cap fan, then the end-cap fan. Winding is outward
  throughout: the start cap faces ``-tangent`` and the end cap
  ``+tangent``.
* A closed loop drops the duplicate ring and both caps: ring *R*-1's
  quads wrap onto ring 0, so ``V = R*M`` and ``F = 2*R*M``. Only a
  ``wrap`` path is a loop today; closing a general chain waits on the
  end frame, which transport does not bring back in general.

What this build evaluates is a circle or polygon profile swept along a
chain of ``line``, ``arc`` and ``helix`` primitives, or around a
``wrap``. ``spline`` raises :class:`NotImplementedError` naming itself
rather than guessing; the spline batch fills it in against fixtures.
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
    """The path as ``k * segments + 1`` frames, ``segments`` per primitive.

    Returns the ring centres ``(R, 3)`` and their profile axes ``(R, 2, 3)``.

    ``tessellation.path`` is spent on every primitive of the chain rather
    than divided among them: an arc-length-proportional split would make
    the ring count follow a parameter, which declared tessellation
    forbids. A primitive begins where its predecessor ended -- no
    primitive says where it starts -- so the ring at a joint is sampled
    once, by the primitive that leaves it, and the frame carried across
    is exactly the identity when the tangents agree.
    """
    frame = START_FRAME
    centres, axes = [], []
    for index, primitive in enumerate(path):
        loc = f"path[{index}]"
        kind = primitive["type"]
        sampler = _SAMPLERS.get(kind)
        if sampler is None:
            raise NotImplementedError(
                f"{loc}: the '{kind}' path primitive is not implemented yet; this "
                f"molejo build evaluates 'line', 'arc', 'helix' and 'wrap' only"
            )
        primitive_centres, primitive_axes, frame = sampler(
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


def _sample_arc(primitive, values, segments, frame, loc):
    """The current point turned about the axis line through ``center``.

    Only the component of ``start - center`` across the axis turns, so
    ``center`` names an axis line rather than a point the arc must reach.
    Ring *i* of *N* sits at ``phi = i*angle/N`` on that circle, and the
    tangent is the circle's, signed by the direction of the turn.
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
    tangential = np.cross(axis, radial)
    turn = angle * np.arange(segments + 1, dtype=np.float64) / segments
    cosine = np.cos(turn)[:, None]
    sine = np.sin(turn)[:, None]

    centres = center + axial + radius * (cosine * radial + sine * tangential)
    sign = 1.0 if angle > 0.0 else -1.0
    tangents = sign * (cosine * tangential - sine * radial)
    axes, frame = _carried(frame, centres, tangents)
    return centres, axes, frame


def _sample_helix(primitive, values, segments, frame, loc):
    """A helix winding about the incoming tangent, from the current point.

    Its axis is the line through ``origin - radius * x`` along the
    tangent, so the helix starts exactly where the path is; it winds
    right-handed (the frame's *x* turning toward its *y*) and advances
    ``height`` over ``turns`` turns. The speed is constant, so rings
    uniform in the turn parameter are uniform in arc length.
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

    axis_point = frame.origin - radius * frame.x
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


def _wrap_geometry(primitive, values, segments, loc):
    """The belt's own geometry: ring centres, tangents, and arc lengths.

    A wrap is planar -- it lies in the world XY plane, because its
    circles are declared there -- and it runs the external tangents,
    clockwise seen from ``+Z``, touching every circle along its outward
    normal. For consecutive circles at distance *L* with radii *r* and
    *r'*, the shared outward normal is

        n = delta*chat + sqrt(1 - delta^2)*rot90(chat),  delta = (r - r')/L

    and the direction of travel is ``(n_y, -n_x)``. The elements of the
    loop are span 0, the arc about circle 1, span 1, … and finally the
    arc about circle 0, each spent ``segments`` rings; the loop's origin
    is where the belt leaves circle 0.
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

    rings = 2 * count * segments
    ring_centres = np.zeros((rings, 3), dtype=np.float64)
    tangents = np.zeros((rings, 3), dtype=np.float64)
    stations = np.empty(rings, dtype=np.float64)
    span_starts = np.empty(count, dtype=np.float64)
    steps = np.arange(segments, dtype=np.float64) / segments

    travelled = 0.0
    at = 0
    for index in range(count):
        following = (index + 1) % count
        normal = normals[index]

        # The tangent span, from circle `index` to circle `following`.
        start = centres[index] + radii[index] * normal
        end = centres[following] + radii[following] * normal
        length = float(np.linalg.norm(end - start))
        span_starts[index] = travelled
        ring_centres[at : at + segments, :2] = start + steps[:, None] * (end - start)
        tangents[at : at + segments, 0] = normal[1]
        tangents[at : at + segments, 1] = -normal[0]
        stations[at : at + segments] = travelled + steps * length
        travelled += length
        at += segments

        # The arc about circle `following`, clockwise from the normal the
        # belt arrives on to the one it leaves on.
        arrival = math.atan2(normal[1], normal[0])
        departure = math.atan2(normals[following][1], normals[following][0])
        turn = (arrival - departure) % (2.0 * math.pi)
        radius = radii[following]
        angles = arrival - turn * steps
        cosine = np.cos(angles)
        sine = np.sin(angles)
        ring_centres[at : at + segments, 0] = centres[following][0] + radius * cosine
        ring_centres[at : at + segments, 1] = centres[following][1] + radius * sine
        tangents[at : at + segments, 0] = sine
        tangents[at : at + segments, 1] = -cosine
        stations[at : at + segments] = travelled + steps * (radius * turn)
        travelled += radius * turn
        at += segments

    return {
        "centres": ring_centres,
        "tangents": tangents,
        "stations": stations,
        "length": travelled,
        "span_starts": span_starts,
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


def _wrap_displacement(primitive, values, segments, loc):
    """How far each ring's inner face is pushed toward the circles.

    Teeth are a periodic trapezoid in arc length whose period is the
    loop's length over the declared count: an integer count over the
    whole loop is what closes the pattern at the seam, and what keeps a
    moving idler changing the tooth pitch *length* rather than the tooth
    count. One period is a quarter crest centred on the pattern origin, a
    quarter ramp, a quarter root and a quarter ramp back. The declared
    ``teeth.pitch`` is the nominal pitch of the belt standard and is not
    read here (see design.md, "The wrap").

    The origin is ``anchor`` (a distance along a named tangent span, so a
    belt clamped to a carriage keeps its teeth meshed as the carriage
    runs), or ``phase`` (belt travel from the wrap's own origin), or the
    wrap's own origin when the document names neither.
    """
    teeth = primitive.get("teeth")
    anchor = primitive.get("anchor")
    if teeth is None and anchor is None and "phase" not in primitive:
        return None

    wrap = _wrap_geometry(primitive, values, segments, loc)
    origin = 0.0
    if anchor is not None:
        origin = wrap["span_starts"][anchor["span"]] + _resolve(
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

    period = wrap["length"] / teeth["count"]
    fraction = ((wrap["stations"] - origin) / period) % 1.0
    distance = np.minimum(fraction, 1.0 - fraction)
    return height * np.clip((0.375 - distance) * 4.0, 0.0, 1.0)


#: The path primitives this build evaluates. A primitive missing from here
#: is valid v1 vocabulary that raises naming itself.
_SAMPLERS = {
    "line": _sample_line,
    "arc": _sample_arc,
    "helix": _sample_helix,
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
    # A wrap is a closed loop and validation has already made its document
    # say so; closing a chain of other primitives waits on the end frame,
    # which a rotation-minimizing transport does not bring back in general.
    looped = path[0]["type"] == "wrap"
    if document.get("loop", False) and not looped:
        raise NotImplementedError(
            "loop: closing a chain of primitives is not implemented yet; this "
            "molejo build closes the loop of a 'wrap' path only"
        )

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
