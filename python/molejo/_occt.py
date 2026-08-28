# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The OCCT kernel behind :mod:`molejo.brep`, and the only module that
imports OCCT.

Keeping every ``OCP`` name in one place is what makes the extra optional:
:mod:`molejo.brep` imports this module on first use and turns the
``ImportError`` into an error naming the extra, so importing molejo, or
evaluating a mesh, never touches a CAD kernel.

The constructions, primitive by primitive, are the exact ones design.md
pins:

* ``line`` is an edge between two points; ``arc`` is an edge on the
  circle its axis and start point define.
* ``wrap`` is the chain of external tangent lines and the arcs between
  them, in the world XY plane.

Sweeping is ``BRepOffsetAPI_MakePipeShell`` under the corrected-Frenet
trihedron law, which removes the torsion twist a plain Frenet frame
carries and so reproduces the mesh evaluators' rotation-minimizing
transport (see design.md, "The trihedron law and the OCCT binding").

A wrap does not sweep at all. Its profile's local *y* is world ``+Z`` at
every station, so a belt of rectangular section is a **prism**: the
region between the trace of its inner face and the trace of its outer
one, extruded by the section's width. That is exact where the mesh is
only sampled, it is the one construction that can carry teeth -- a sweep
has a constant section by definition -- and it is why a belt's faces come
back as planes and cylinders instead of a fitted surface.
"""

import math

import numpy as np

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.GProp import GProp_GProps
from OCP.TColgp import TColgp_HArray1OfPnt
from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import (
    gp_Ax2,
    gp_Circ,
    gp_Dir,
    gp_Pln,
    gp_Pnt,
    gp_Vec,
)

from .brep import APPROXIMATION, BrepError, BrepResult
from .evaluator import (
    START_FRAME,
    EvaluationError,
    Frame,
    _arc_geometry,
    _describe,
    _looped,
    _modulation,
    _profile_points,
    _resolve,
    _resolve_vector,
    _wrap_circles,
    _wrap_elements,
    _wrap_pattern,
    transport,
)
from .spec import validate

#: The surface classes that are closed form. A result declaring a zero
#: approximation tolerance may carry nothing else.
ANALYTIC = frozenset({"Plane", "Cylinder", "Cone", "Sphere", "Torus"})

#: The relative error the adaptive Gauss integration of volume and area is
#: driven to. OCCT's non-adaptive default integrates a swept B-spline face
#: badly enough to lose four digits of a tube's volume, which would make
#: every property assertion a statement about the integrator rather than
#: about the shape.
_INTEGRATION = 1e-9

#: How finely an Archimedean spiral -- a tooth ramp crossing an arc -- is
#: interpolated, in radians of the arc it rides. The interpolation is a C2
#: cubic through points *on* the spiral, so its departure falls as the
#: fourth power of this step; at this value it is under 1e-7 for belts of
#: pulley size, two orders inside the declared tolerance.
_SPIRAL_STEP = 0.02


# --- small conversions ------------------------------------------------------


def _pnt(vector, z=None):
    return gp_Pnt(
        float(vector[0]), float(vector[1]), float(vector[2]) if z is None else float(z)
    )


def _dir(vector, z=None):
    return gp_Dir(
        float(vector[0]), float(vector[1]), float(vector[2]) if z is None else float(z)
    )


def _wire(edges):
    builder = BRepBuilderAPI_MakeWire()
    for edge in edges:
        builder.Add(edge)
    return builder.Wire()


def _faces(shape):
    found = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        found.append(TopoDS.Face_s(explorer.Current()))
        explorer.Next()
    return found


def _shells(shape):
    found = []
    explorer = TopExp_Explorer(shape, TopAbs_SHELL)
    while explorer.More():
        found.append(TopoDS.Shell_s(explorer.Current()))
        explorer.Next()
    return found


# --- what a caller asks of a result -----------------------------------------


def volume(solid):
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, properties, _INTEGRATION)
    return properties.Mass()


def area(solid):
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(solid, properties, _INTEGRATION)
    return properties.Mass()


def surfaces(solid):
    """Each face's surface class as a plain name, in face order."""
    return tuple(
        BRepAdaptor_Surface(face).GetType().name.removeprefix("GeomAbs_")
        for face in _faces(solid)
    )


def is_closed(solid):
    """One valid shell with no free boundary: a solid worth asserting on."""
    shells = _shells(solid)
    return (
        len(shells) == 1
        and bool(shells[0].Closed())
        and bool(BRepCheck_Analyzer(solid).IsValid())
    )


# --- the profile ------------------------------------------------------------


def _profile_wire(profile, values, count, frame):
    """The declared profile as a closed wire, drawn in ``frame``.

    A circle profile is a *circle*, not the M-gon the tessellation asks
    the mesh evaluator to sample: `tessellation.profile` is a sampling
    instruction and this evaluation does not sample. A polygon profile is
    its declared points, which are the shape itself either way.
    """
    if profile["type"] == "circle":
        radius = _resolve(profile["radius"], values, "profile.radius")
        if radius <= 0.0:
            raise EvaluationError(
                f"profile.radius: must be a positive number, got {_describe(radius)}"
            )
        circle = gp_Circ(
            gp_Ax2(_pnt(frame.origin), _dir(frame.tangent), _dir(frame.x)), radius
        )
        return _wire([BRepBuilderAPI_MakeEdge(circle).Edge()])

    points = _profile_points(profile, values, count)
    polygon = BRepBuilderAPI_MakePolygon()
    for across, along in points:
        polygon.Add(_pnt(frame.origin + across * frame.x + along * frame.y))
    polygon.Close()
    return polygon.Wire()


def _rectangle(points):
    """The section's ``(x_lo, x_hi, y_lo, y_hi)`` if it is a rectangle.

    A toothed belt is only a prism when its section is one: the teeth
    displace the vertices at the minimum local *x*, and the extrusion
    along local *y* is the same at every station only if the section's
    *y* extent does not depend on *x*.
    """
    if len(points) != 4:
        return None
    across = np.unique(points[:, 0])
    along = np.unique(points[:, 1])
    if len(across) != 2 or len(along) != 2:
        return None
    corners = {(float(u), float(v)) for u in across for v in along}
    if {(float(u), float(v)) for u, v in points} != corners:
        return None
    return float(across[0]), float(across[1]), float(along[0]), float(along[1])


# --- the path, primitive by primitive ---------------------------------------
#
# Every builder answers with its edges, the frame the profile stands in at
# its start, the frame the path has reached at its end, and whether it
# forced an approximation anywhere.


def _line_edges(primitive, values, frame, loc):
    start = frame.origin
    end = _resolve_vector(primitive["to"], values, f"{loc}.to")
    direction = end - start
    length = float(np.linalg.norm(direction))
    if length <= 0.0:
        raise EvaluationError(
            f"{loc}.to: a line must go somewhere; its end coincides with its start"
        )
    entry = transport(frame, direction / length, start)
    exit_frame = Frame(end, entry.x, entry.y, entry.tangent)
    return [BRepBuilderAPI_MakeEdge(_pnt(start), _pnt(end)).Edge()], entry, exit_frame, False


def _arc_edges(primitive, values, frame, loc):
    arc = _arc_geometry(primitive, values, frame, loc)
    radius, radial, tangential = arc["radius"], arc["radial"], arc["tangential"]
    angle = arc["angle"]
    sign = 1.0 if angle > 0.0 else -1.0

    # Right-handed about the axis by a negative angle is right-handed about
    # the reversed axis by its magnitude, so one construction covers both
    # directions and the arc always starts at the path's current point.
    axes = gp_Ax2(_pnt(arc["centre"]), _dir(sign * arc["axis"]), _dir(radial))
    edge = BRepBuilderAPI_MakeEdge(
        GC_MakeArcOfCircle(gp_Circ(axes, radius), 0.0, abs(angle), True).Value()
    ).Edge()

    cosine, sine = math.cos(angle), math.sin(angle)
    end = arc["centre"] + radius * (cosine * radial + sine * tangential)
    # Every tangent of a circular arc lies in the plane across its axis, so
    # the composed rotation-minimizing transport is the single rotation
    # through the total angle: exact, not an approximation of the mesh's.
    entry = transport(frame, sign * tangential, frame.origin)
    exit_frame = transport(frame, sign * (cosine * tangential - sine * radial), end)
    return [edge], entry, exit_frame, False


#: The path primitives this build constructs exactly. One missing from
#: here is valid v1 vocabulary that raises naming itself.
_EDGES = {
    "line": _line_edges,
    "arc": _arc_edges,
}


def _swept_solid(path, profile, values, count):
    """A profile carried along an open chain, capped at both ends.

    The frame the profile stands in is the start frame carried onto the
    first primitive's own start tangent, exactly as the mesh evaluator's
    ring 0 is, and the sweep then transports it under the corrected-Frenet
    law. For a circular profile the roll about the tangent is invisible;
    for any other it is the law's, which is the continuous limit of the
    mesh's ring-by-ring composition.
    """
    frame = START_FRAME
    edges = []
    entry = None
    approximated = False
    for index, primitive in enumerate(path):
        builder = _EDGES.get(primitive["type"])
        if builder is None:
            raise NotImplementedError(
                f"path[{index}]: the '{primitive['type']}' primitive has no exact "
                f"construction in this molejo build yet"
            )
        made, at_start, frame, rough = builder(
            primitive, values, frame, f"path[{index}]"
        )
        edges.extend(made)
        entry = at_start if entry is None else entry
        approximated = approximated or rough

    shell = BRepOffsetAPI_MakePipeShell(_wire(edges))
    # False is the corrected Frenet law: the Frenet trihedron with its
    # torsion twist removed, which is what reproduces the pinned no-twist
    # transport (see design.md).
    shell.SetMode(False)
    shell.SetTolerance(APPROXIMATION, APPROXIMATION, 1e-4)
    shell.Add(_profile_wire(profile, values, count, entry), False, False)
    shell.Build()
    if not shell.MakeSolid():
        raise BrepError("the swept shell could not be closed into a solid")
    return shell.Shape(), (APPROXIMATION if approximated else 0.0)


# --- the belt ---------------------------------------------------------------


def _wrap_edges(elements, height):
    """The wrap's own chain of lines and arcs, at world height ``height``."""
    edges = []
    for element in elements:
        if element["kind"] == "span":
            edges.append(
                BRepBuilderAPI_MakeEdge(
                    _pnt(element["start"], height), _pnt(element["end"], height)
                ).Edge()
            )
        else:
            edges.append(_arc_edge(element, element["radius"], element["from"],
                                   element["turn"], height))
    return edges


def _arc_edge(element, radius, start_angle, turn, height):
    """One clockwise arc about a circle's centre, at world height ``height``."""
    axes = gp_Ax2(
        _pnt(element["centre"], height),
        gp_Dir(0.0, 0.0, -1.0),
        gp_Dir(math.cos(start_angle), math.sin(start_angle), 0.0),
    )
    return BRepBuilderAPI_MakeEdge(
        GC_MakeArcOfCircle(gp_Circ(axes, radius), 0.0, turn, True).Value()
    ).Edge()


def _trace_point(element, distance, across):
    """A point of the belt's trace at local *x* = ``across``."""
    if element["kind"] == "span":
        normal = element["normal"]
        along = np.array([normal[1], -normal[0]])
        return element["start"] + distance * along + across * normal
    angle = element["from"] - distance / element["radius"]
    return element["centre"] + (element["radius"] + across) * np.array(
        [math.cos(angle), math.sin(angle)]
    )


def _tooth_breaks(origin, period, total):
    """Where the trapezoid changes slope, in arc length around the loop.

    The quarter marks 0.125, 0.375, 0.625 and 0.875 of every period, and
    nowhere else: the period boundary falls in the middle of a crest and
    the half falls in the middle of a root, so neither is a corner.
    """
    breaks = []
    first = math.floor((0.0 - origin) / period) - 1
    last = math.ceil((total - origin) / period) + 1
    for turn in range(first, last):
        for quarter in (0.125, 0.375, 0.625, 0.875):
            station = origin + (turn + quarter) * period
            if 0.0 < station < total:
                breaks.append(station)
    return sorted(breaks)


def _trace_wire(elements, total, across, height, pattern):
    """The closed trace of one face of the belt, and whether it spiralled.

    Cut at every tooth corner, each piece has a displacement linear in arc
    length, and each piece is then exact or not according to what it rides:

    * on a straight span the trace stays straight, because the normal is
      constant and the offset is linear -- a tooth flank is a line;
    * on an arc with the displacement constant -- a crest, a root, or a
      toothless belt -- the trace is a circle of the offset radius;
    * on an arc with the displacement ramping, ``r = a + b*theta`` is an
      Archimedean spiral, which no NURBS holds exactly. That piece alone
      is interpolated, and that piece alone is why a toothed belt declares
      a tolerance.
    """
    breaks = _tooth_breaks(pattern[0], pattern[1], total) if pattern else []

    def offset(station):
        if pattern is None:
            return across
        return across - pattern[2] * float(_modulation(station, pattern[0], pattern[1]))

    edges = []
    spiralled = False
    for element in elements:
        start, length = element["station"], element["length"]
        cuts = [start]
        cuts += [b for b in breaks if start < b < start + length]
        cuts.append(start + length)
        for here, there in zip(cuts[:-1], cuts[1:]):
            near, far = offset(here), offset(there)
            if element["kind"] == "span":
                edges.append(
                    BRepBuilderAPI_MakeEdge(
                        _pnt(_trace_point(element, here - start, near), height),
                        _pnt(_trace_point(element, there - start, far), height),
                    ).Edge()
                )
            elif near == far:
                edges.append(
                    _arc_edge(
                        element,
                        element["radius"] + near,
                        element["from"] - (here - start) / element["radius"],
                        (there - here) / element["radius"],
                        height,
                    )
                )
            else:
                spiralled = True
                edges.append(
                    _spiral_edge(element, start, here, there, offset, height)
                )
    return _wire(edges), spiralled


def _spiral_edge(element, start, here, there, offset, height):
    """One Archimedean ramp, interpolated to the declared tolerance.

    A C2 cubic through points *on* the spiral, so the curve hits both ends
    exactly -- which is what keeps the wire closed -- and departs between
    them by O(step^4).
    """
    turn = abs(there - here) / element["radius"]
    steps = max(4, int(math.ceil(turn / _SPIRAL_STEP)))
    array = TColgp_HArray1OfPnt(1, steps + 1)
    for index in range(steps + 1):
        station = here + (there - here) * index / steps
        array.SetValue(
            index + 1,
            _pnt(_trace_point(element, station - start, offset(station)), height),
        )
    interpolate = GeomAPI_Interpolate(array, False, APPROXIMATION * 1e-3)
    interpolate.Perform()
    if not interpolate.IsDone():
        raise BrepError("a tooth ramp crossing an arc could not be interpolated")
    return BRepBuilderAPI_MakeEdge(interpolate.Curve()).Edge()


def _belt_prism(elements, total, section, pattern):
    """The band between the belt's two traces, extruded by its width.

    Exact wherever the traces are, which is everywhere but a ramp crossing
    an arc. The outer trace carries no teeth by construction -- teeth
    displace the inner face only -- so it is always lines and arcs.
    """
    across_lo, across_hi, along_lo, along_hi = section
    outer, _ = _trace_wire(elements, total, across_hi, along_lo, None)
    inner, spiralled = _trace_wire(elements, total, across_lo, along_lo, pattern)

    face = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(0.0, 0.0, along_lo), gp_Dir(0.0, 0.0, 1.0)), outer
    )
    face.Add(inner)
    solid = BRepPrimAPI_MakePrism(
        face.Face(), gp_Vec(0.0, 0.0, along_hi - along_lo)
    ).Shape()
    return solid, (APPROXIMATION if spiralled else 0.0)


def _wrap_solid(primitive, profile, values, count, loc):
    """A belt: a prism where its section is rectangular, a sweep otherwise."""
    centres, radii, normals = _wrap_circles(primitive, values, loc)
    elements, total = _wrap_elements(centres, radii, normals)
    pattern = _wrap_pattern(primitive, values, elements, total, loc)

    section = None
    if profile["type"] == "polygon":
        section = _rectangle(_profile_points(profile, values, count))
    if section is not None:
        return _belt_prism(elements, total, section, pattern)

    if pattern is not None:
        raise NotImplementedError(
            f"{loc}.teeth: an exact toothed belt needs a rectangular section, "
            f"because the teeth displace the profile's inner face along the loop "
            f"and only a rectangle extrudes the same way at every station"
        )

    # No teeth, so the section is constant and an ordinary sweep along the
    # closed wrap chain is exact: cylinders on the spans, tori on the arcs.
    normal = elements[0]["normal"]
    frame = Frame(
        origin=np.array([elements[0]["start"][0], elements[0]["start"][1], 0.0]),
        x=np.array([normal[0], normal[1], 0.0]),
        y=np.array([0.0, 0.0, 1.0]),
        tangent=np.array([normal[1], -normal[0], 0.0]),
    )
    shell = BRepOffsetAPI_MakePipeShell(_wire(_wrap_edges(elements, 0.0)))
    shell.SetMode(False)
    shell.SetTolerance(APPROXIMATION, APPROXIMATION, 1e-4)
    shell.Add(_profile_wire(profile, values, count, frame), False, False)
    shell.Build()
    if not shell.MakeSolid():
        raise BrepError("the belt's shell could not be closed into a solid")
    return shell.Shape(), 0.0


# --- the evaluation ---------------------------------------------------------


def build(document, values=None):
    """Evaluate a molejo document to a closed solid at the given values."""
    validate(document)
    values = {} if values is None else values

    path = document["path"]
    count = document["tessellation"]["profile"]
    profile = document["profile"]

    if _looped(document):
        solid, tolerance = _wrap_solid(path[0], profile, values, count, "path[0]")
    else:
        solid, tolerance = _swept_solid(path, profile, values, count)

    return BrepResult(_vouched(solid, tolerance), tolerance)


def _vouched(solid, tolerance):
    """The solid, or the reason it is not one worth asserting on.

    Two promises are checked here rather than assumed. The result is one
    valid closed shell -- a sweep of a closed profile admits no hole, and
    if OCCT ever hands back one anyway the caller hears about it. And a
    result claiming a zero approximation tolerance really carries no
    approximated surface, which is the whole of "exactness is stated
    honestly": the evaluator may not quietly degrade an analytically
    representable sweep and still call it exact.
    """
    if not is_closed(solid):
        raise BrepError(
            "the construction did not produce one closed shell; molejo returns no "
            "partial or unclosed solid"
        )
    if tolerance == 0.0:
        rough = sorted({name for name in surfaces(solid) if name not in ANALYTIC})
        if rough:
            raise BrepError(
                f"the construction declared an exact solid but carries "
                f"{', '.join(rough)}; an approximated surface must declare its "
                f"tolerance"
            )
    solid.Closed(True)
    return solid
