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
* ``tessellation.path`` is a segment count *N*: an open path has
  ``N + 1`` rings. Wall vertex ``ring*M + j``; then the start-cap centre,
  then the end-cap centre.
* Faces run walls first (ring-major, then *j*, two triangles a quad),
  then the start-cap fan, then the end-cap fan. Winding is outward
  throughout: the start cap faces ``-tangent`` and the end cap
  ``+tangent``.

What this build evaluates is the circle profile swept along a single
line. Every other primitive raises :class:`NotImplementedError` naming
itself rather than guessing; the arc, helix, wrap and spline batches
fill them in against fixtures.
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


def _profile_points(profile, values, count):
    """The profile as ``(count, 2)`` coordinates in the profile frame."""
    kind = profile["type"]
    if kind != "circle":
        raise NotImplementedError(
            f"profile: the '{kind}' profile is not implemented yet; this molejo "
            f"build evaluates 'circle' only"
        )
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


# --- paths -----------------------------------------------------------------


def _sample_path(path, values, segments):
    """The path as ``segments + 1`` frames, evenly spaced along it.

    Returns the ring centres ``(R, 3)`` and their profile axes ``(R, 2, 3)``.
    """
    if len(path) != 1:
        raise NotImplementedError(
            f"path: this molejo build does not distribute tessellation.path across "
            f"a multi-primitive path ({len(path)} primitives) yet"
        )
    primitive = path[0]
    kind = primitive["type"]
    if kind != "line":
        raise NotImplementedError(
            f"path[0]: the '{kind}' path primitive is not implemented yet; this "
            f"molejo build evaluates 'line' only"
        )
    return _sample_line(primitive, values, segments, START_FRAME, "path[0]")


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
    frame = transport(frame, direction / length)

    steps = np.arange(segments + 1, dtype=np.float64) / segments
    centres = start + steps[:, None] * direction
    axes = np.empty((segments + 1, 2, 3), dtype=np.float64)
    axes[:, 0, :] = frame.x
    axes[:, 1, :] = frame.y
    return centres, axes


# --- mesh assembly ---------------------------------------------------------


def _wall_vertices(centres, axes, points):
    """Ring-major wall vertices: ``ring*M + j``, in the ring's own frame."""
    u = points[:, 0]
    v = points[:, 1]
    return (
        centres[:, None, :]
        + u[None, :, None] * axes[:, None, 0, :]
        + v[None, :, None] * axes[:, None, 1, :]
    )


def _faces(rings, count):
    """Walls (ring-major), then the start-cap fan, then the end-cap fan."""
    j = np.arange(count, dtype=np.int64)
    following = (j + 1) % count
    ring = np.arange(rings - 1, dtype=np.int64)[:, None] * count

    a = ring + j[None, :]
    b = ring + following[None, :]
    c = b + count
    d = a + count
    quads = np.empty((rings - 1, count, 2, 3), dtype=np.int32)
    quads[:, :, 0, 0] = a
    quads[:, :, 0, 1] = b
    quads[:, :, 0, 2] = c
    quads[:, :, 1, 0] = a
    quads[:, :, 1, 1] = c
    quads[:, :, 1, 2] = d

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

    if document.get("loop", False):
        raise NotImplementedError(
            "loop: closed-loop paths are not implemented yet; this molejo build "
            "evaluates open paths only"
        )

    count = document["tessellation"]["profile"]
    segments = document["tessellation"]["path"]

    # Everything a parameter can touch is resolved before a single vertex is
    # written, which is what makes "no partial output" true rather than hoped.
    points = _profile_points(document["profile"], values, count)
    centres, axes = _sample_path(document["path"], values, segments)

    rings = len(centres)
    vertices = np.empty((rings * count + 2, 3), dtype=np.float64)
    vertices[: rings * count] = _wall_vertices(centres, axes, points).reshape(-1, 3)
    vertices[rings * count] = centres[0]
    vertices[rings * count + 1] = centres[-1]

    return Mesh(vertices=vertices, faces=_faces(rings, count))
