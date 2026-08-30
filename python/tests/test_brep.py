# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The B-rep evaluator: the same document, evaluated exactly.

The originating consumer asserts on exact shapes, so a molejo document
has to reach OCCT without passing through a mesh. That is the whole point
of this module: nothing here samples anything. A line is an edge, an arc
is an edge on a circle, a wrap is a chain of tangent lines and arcs, and
the profile is the analytic profile the document declares -- a true
circle, not the M-gon `tessellation.profile` asks the mesh evaluator for.

Two claims are held to account here rather than merely stated. The first
is exactness: a sweep along lines and arcs must come back as planes,
cylinders and toroidal patches with the declared approximation tolerance
at exactly zero, and the evaluator must refuse to hand back an
approximated surface where an analytic one exists. The second is that the
B-rep is *nearer truth* than the facets, which is why every assertion
below compares it against an independent closed form -- the tube volume
pi*a^2*L, the shoelace prism a planar belt encloses -- at a tolerance the
mesh could not dream of meeting.

The closed forms are written here from design.md rather than borrowed
from the evaluator, exactly as the mesh suites' are. The belt's is the
strongest: a planar wrap of rectangular section sweeps the region between
its inner and outer traces, and both traces decompose into straight
chords and pieces of r = a + b*theta about a circle's centre -- one
integral covering the exact arc, the tooth crest, the tooth root, and the
Archimedean spiral a ramp traces where it crosses an arc.
"""

import math

import numpy as np
import pytest

pytest.importorskip("OCP", reason="the brep extra is not installed")

from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
from OCP.gp import gp_Pnt

import molejo
from molejo import Circle, Line, P, Polygon, Shape, Teeth, Wrap
from molejo.brep import APPROXIMATION, BrepError, BrepResult
from molejo.evaluator import EvaluationError

from test_evaluation import cylinder, slanted
from test_curved_paths import (
    QUARTER,
    bend,
    elbow,
    helix_centres,
    helix_length,
    helix_tangents,
    spring,
    tube_volume,
)
from test_spline import hermite_rings, hermite_tangents, loom, loom_points, NEAR
from test_wrap import CARRIAGE, PULLEYS, SECTION, belt, elements, modulation, toothed

TAU = 2.0 * math.pi

#: The analytic surface classes: nothing here is an approximation.
ANALYTIC = {"Plane", "Cylinder", "Cone", "Sphere", "Torus"}


def brep(document, values=None):
    return molejo.brep.evaluate(document, values)


# --- independent closed forms ----------------------------------------------


def stationed(circles):
    """The wrap's 2k elements, each carrying the station it starts at."""
    items, travelled = [], 0.0
    for item in elements(circles):
        items.append(dict(item, s0=travelled))
        travelled += item["length"]
    return items, travelled


def tooth_breaks(origin, period, total):
    """Where the trapezoid changes slope, in arc length around the loop.

    One period is a quarter crest centred on the origin, a quarter ramp, a
    quarter root and a quarter ramp back, so the slope changes at the
    quarter marks 0.125, 0.375, 0.625 and 0.875 -- and nowhere else, the
    period boundary itself falling in the middle of a crest.
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


def trace_point(item, distance, across):
    """A point of the belt's trace at local *x* = ``across``.

    On an arc the profile's local *x* is the circle's outward radial
    where the belt turns clockwise about it and its inward radial where
    the belt turns the other way, so the offset is signed by the sense,
    and so is the way the angle advances.
    """
    if item["kind"] == "span":
        normal = item["normal"]
        along = np.array([normal[1], -normal[0]])
        return item["start"] + distance * along + across * normal
    sense = item["sense"]
    angle = item["from"] - sense * distance / item["radius"]
    return item["centre"] + (item["radius"] + sense * across) * np.array(
        [math.cos(angle), math.sin(angle)]
    )


def trace_area(circles, across, teeth=None, origin=0.0, toward=-1.0):
    """The signed area the belt's trace at local *x* encloses.

    Green's theorem, piece by piece. A span's trace is straight even where
    a tooth ramps along it -- the offset is linear in arc length and the
    normal is constant -- so it contributes the surveyor's triangle. On an
    arc the trace is ``r = a + b*theta`` about the circle's centre, whose
    Green integrand is ``r^2 + d/dtheta(c_x * r sin - c_y * r cos)``: the
    centre terms collapse to their endpoint values, and ``int r^2`` is
    ``(tb - ta) * (ra^2 + ra*rb + rb^2)/3`` -- the form that stays exact
    when the two radii are equal, which the difference of cubes does not.
    """
    items, total = stationed(circles)
    period = total / teeth["count"] if teeth else None
    breaks = tooth_breaks(origin, period, total) if teeth else []

    def offset(station):
        if teeth is None:
            return across
        return across + toward * teeth["height"] * modulation(
            station, origin, period
        )

    area = 0.0
    for item in items:
        start, length = item["s0"], item["length"]
        cuts = [start] + [b for b in breaks if start < b < start + length] + [
            start + length
        ]
        for here, there in zip(cuts[:-1], cuts[1:]):
            near, far = offset(here), offset(there)
            if item["kind"] == "span":
                a = trace_point(item, here - start, near)
                b = trace_point(item, there - start, far)
                area += 0.5 * (a[0] * b[1] - b[0] * a[1])
                continue
            centre, radius, sense = item["centre"], item["radius"], item["sense"]
            ta = item["from"] - sense * (here - start) / radius
            tb = item["from"] - sense * (there - start) / radius
            ra, rb = radius + sense * near, radius + sense * far
            area += 0.5 * (
                (tb - ta) * (ra * ra + ra * rb + rb * rb) / 3.0
                + centre[0] * (rb * math.sin(tb) - ra * math.sin(ta))
                + centre[1] * (ra * math.cos(ta) - rb * math.cos(tb))
            )
    return area


def belt_volume(circles, section=SECTION, teeth=None, origin=0.0, face="inner"):
    """The exact prism a planar belt of rectangular section encloses.

    Exactly one of the two traces carries the teeth -- a belt has them on
    one face -- and which one is `face`.
    """
    points = np.asarray(section, dtype=np.float64)
    width = points[:, 1].max() - points[:, 1].min()
    outer = trace_area(
        circles,
        points[:, 0].max(),
        teeth if face == "outer" else None,
        origin,
        toward=+1.0,
    )
    inner = trace_area(
        circles,
        points[:, 0].min(),
        None if face == "outer" else teeth,
        origin,
    )
    return width * (abs(outer) - abs(inner))


def loop_length(circles):
    return stationed(circles)[1]


def hermite_length(points, **kwargs):
    """The arc length of a Hermite chain, by Gauss-Legendre quadrature.

    The velocity of a cubic is a quadratic, so its norm is smooth and a
    high-order rule is exact to machine precision on every span. That
    makes ``pi*a^2*L`` an independent expectation for a swept spline, with
    nothing borrowed from OCCT or from the evaluator.
    """
    points = np.asarray(points, dtype=np.float64)
    tangents = hermite_tangents(points, **kwargs)
    nodes, weights = np.polynomial.legendre.leggauss(200)
    step = 0.5 * (nodes + 1.0)
    weights = 0.5 * weights
    square = step * step
    total = 0.0
    for index in range(len(points) - 1):
        velocity = (
            (6.0 * square - 6.0 * step)[:, None] * (points[index] - points[index + 1])
            + (3.0 * square - 4.0 * step + 1.0)[:, None] * tangents[index]
            + (3.0 * square - 2.0 * step)[:, None] * tangents[index + 1]
        )
        total += float(np.sum(weights * np.linalg.norm(velocity, axis=1)))
    return total


def where(result, point):
    """Whether a point is inside the solid, outside it, or on its skin."""
    classifier = BRepClass3d_SolidClassifier(result.solid)
    classifier.Perform(gp_Pnt(*(float(value) for value in point)), 1e-9)
    return classifier.State()


def perpendicular(tangent):
    axis = np.zeros(3)
    axis[int(np.argmin(np.abs(tangent)))] = 1.0
    across = np.cross(tangent, axis)
    return across / np.linalg.norm(across)


def assert_tube_about(result, centres, tangents, radius):
    """The solid is the tube of ``radius`` about the given curve.

    Every sampled point of the curve is inside it and every point pushed
    a little past the wall is outside, which pins the *path* rather than
    just its length: a solid of the right volume about the wrong curve
    fails here.
    """
    for centre, tangent in zip(centres[1:-1], tangents[1:-1]):
        across = perpendicular(tangent)
        assert where(result, centre) == TopAbs_IN
        assert where(result, centre + 0.99 * radius * across) == TopAbs_IN
        assert where(result, centre + 1.01 * radius * across) == TopAbs_OUT


# --- one closed solid -------------------------------------------------------


def test_a_cylinder_is_one_closed_solid():
    result = brep(cylinder(radius=5.0, length=12.0))
    assert isinstance(result, BrepResult)
    assert result.is_closed()


def test_the_cylinder_encloses_the_analytic_volume():
    # Not the prism of the declared tessellation, which is what the mesh
    # encloses: the exact cylinder the document describes.
    result = brep(cylinder(radius=5.0, length=12.0, profile=12))
    assert result.volume() == pytest.approx(math.pi * 25.0 * 12.0, rel=1e-12)


def test_the_cylinder_carries_the_analytic_area():
    result = brep(cylinder(radius=5.0, length=12.0, profile=12))
    assert result.area() == pytest.approx(
        2.0 * math.pi * 5.0 * 12.0 + 2.0 * math.pi * 25.0, rel=1e-12
    )


def test_the_declared_tessellation_does_not_move_the_solid():
    # `tessellation` is the mesh evaluator's sampling instruction. An exact
    # evaluation must not read it as geometry.
    coarse = brep(cylinder(radius=5.0, length=12.0, path=2, profile=5))
    fine = brep(cylinder(radius=5.0, length=12.0, path=64, profile=256))
    assert coarse.volume() == pytest.approx(fine.volume(), rel=1e-12)


def test_a_parameter_moves_the_solid_and_nothing_else():
    document = cylinder(radius=5.0, length=12.0)
    document["path"][0]["to"][2] = {"param": "length"}
    short = brep(document, {"length": 12.0})
    tall = brep(document, {"length": 40.0})
    assert tall.volume() == pytest.approx(short.volume() * 40.0 / 12.0, rel=1e-12)


def test_evaluation_is_repeatable():
    document = cylinder()
    assert brep(document).volume() == brep(document).volume()


# --- exactness, stated and enforced -----------------------------------------


def test_a_line_sweep_is_a_cylinder_between_two_planes():
    result = brep(cylinder(radius=5.0, length=12.0))
    assert sorted(result.surfaces()) == ["Cylinder", "Plane", "Plane"]
    assert result.tolerance == 0.0


def test_an_oblique_line_still_sweeps_an_exact_tube():
    document = slanted(to=[3.0, 4.0, 12.0], radius=2.5)
    result = brep(document)
    assert set(result.surfaces()) <= ANALYTIC
    assert result.tolerance == 0.0
    assert result.volume() == pytest.approx(
        tube_volume(2.5, math.sqrt(9.0 + 16.0 + 144.0)), rel=1e-12
    )


def test_a_quarter_bend_is_a_cylinder_a_torus_and_a_cylinder():
    result = brep(bend(reach=20.0))
    assert sorted(result.surfaces()) == [
        "Cylinder",
        "Cylinder",
        "Plane",
        "Plane",
        "Torus",
    ]
    assert result.tolerance == 0.0


def test_the_quarter_bend_encloses_the_tube_volume_exactly():
    # pi*a^2*L for a tube about any embedded space curve, so a chain of a
    # line, an arc and a line is checkable without a kernel.
    for reach in (20.0, 40.0):
        length = 10.0 + 6.0 * QUARTER + (reach - 6.0)
        result = brep(bend(reach=reach))
        assert result.volume() == pytest.approx(tube_volume(1.5, length), rel=1e-12)


def test_a_bare_arc_is_a_torus_between_two_planes():
    result = brep(elbow(angle=QUARTER))
    assert sorted(result.surfaces()) == ["Plane", "Plane", "Torus"]
    assert result.volume() == pytest.approx(
        tube_volume(1.5, 6.0 * QUARTER), rel=1e-12
    )


def test_an_arc_that_turns_the_other_way_is_the_mirror_solid():
    forward = brep(elbow(angle=QUARTER))
    backward = brep(elbow(angle=-QUARTER))
    assert backward.volume() == pytest.approx(forward.volume(), rel=1e-12)
    assert sorted(backward.surfaces()) == ["Plane", "Plane", "Torus"]


def test_a_polygon_profile_sweeps_a_prism_of_planes():
    from test_wrap import bar

    result = brep(bar(SECTION, to=(0.0, 0.0, 10.0)))
    assert set(result.surfaces()) == {"Plane"}
    assert result.tolerance == 0.0
    assert result.volume() == pytest.approx(1.3 * 6.0 * 10.0, rel=1e-12)


# --- the helix, on its own cylinder -----------------------------------------


def test_a_spring_is_one_closed_solid():
    result = brep(spring(wire=1.0, radius=6.0, turns=2.5, height=30.0))
    assert result.is_closed()


def test_a_helix_sweep_is_a_tolerance_declared_bspline_between_two_planes():
    # No kernel has a closed form for a surface swept along a helix, so
    # this is the fidelity class OCCT gives any swept feature -- and the
    # result says so rather than implying exactness it does not have.
    result = brep(spring())
    assert sorted(result.surfaces()) == ["BSplineSurface", "Plane", "Plane"]
    assert result.tolerance == APPROXIMATION


def test_the_spring_encloses_the_helix_tube_volume():
    # pi*a^2*L for a tube about any embedded space curve, and a helix's
    # length is hypot(2*pi*turns*radius, height) in closed form.
    for height in (30.0, 12.0):
        result = brep(spring(wire=1.0, radius=6.0, turns=2.5, height=height))
        expected = tube_volume(1.0, helix_length(6.0, 2.5, height))
        assert result.volume() == pytest.approx(expected, rel=1e-6)


def test_the_spring_carries_the_helix_tube_area():
    length = helix_length(6.0, 2.5, 30.0)
    result = brep(spring())
    assert result.area() == pytest.approx(
        2.0 * math.pi * 1.0 * length + 2.0 * math.pi * 1.0, rel=1e-6
    )


def test_the_solid_follows_the_analytic_helix_and_not_a_sampling():
    # The curve is a 2D line on a Geom_CylindricalSurface, so it is the
    # analytic helix at every point rather than a chord chain through
    # `tessellation.path` samples.
    result = brep(spring(wire=1.0, radius=6.0, turns=2.5, height=30.0, path=3))
    assert_tube_about(
        result,
        helix_centres(6.0, 2.5, 30.0, path=60),
        helix_tangents(6.0, 2.5, 30.0, path=60),
        1.0,
    )


def test_the_spring_volume_does_not_follow_the_tessellation():
    coarse = brep(spring(path=3, profile=5))
    fine = brep(spring(path=200, profile=256))
    assert coarse.volume() == pytest.approx(fine.volume(), rel=1e-6)


def test_a_left_handed_helix_is_the_mirror_solid():
    right = brep(spring(turns=2.5))
    left = brep(spring(turns=-2.5))
    assert left.volume() == pytest.approx(right.volume(), rel=1e-6)


def test_a_helix_that_goes_nowhere_is_refused_as_the_mesh_refuses_it():
    document = spring(turns=0.0, height=0.0)
    with pytest.raises(EvaluationError) as caught:
        brep(document)
    with pytest.raises(EvaluationError) as mesh:
        molejo.evaluate(document)
    assert str(caught.value) == str(mesh.value)


# --- the spline, as one B-spline curve --------------------------------------


def test_a_loom_is_one_closed_solid():
    result = brep(loom(), NEAR)
    assert result.is_closed()


def test_a_spline_sweep_is_a_tolerance_declared_bspline_between_two_planes():
    result = brep(loom(), NEAR)
    assert sorted(result.surfaces()) == ["BSplineSurface", "Plane", "Plane"]
    assert result.tolerance == APPROXIMATION


def test_the_loom_encloses_the_hermite_tube_volume():
    result = brep(loom(), NEAR)
    length = hermite_length(
        loom_points(NEAR), start_tangent=[0.0, 1.0, 0.0], end_tangent=[0.0, 0.0, -1.0]
    )
    assert result.volume() == pytest.approx(tube_volume(2.0, length), rel=1e-6)


def test_the_solid_follows_the_hermite_chain_and_not_a_sampling():
    # The exact curve is the C1 chain of Bezier spans as one cubic
    # B-spline, so the closed-form Hermite points must lie on its axis at
    # a resolution the document never declared.
    result = brep(loom(path=3), NEAR)
    centres, tangents = hermite_rings(
        loom_points(NEAR),
        40,
        start_tangent=[0.0, 1.0, 0.0],
        end_tangent=[0.0, 0.0, -1.0],
    )
    assert_tube_about(result, centres, tangents, 2.0)


def test_the_loom_hits_both_declared_ends():
    result = brep(loom(), NEAR)
    points = np.asarray(loom_points(NEAR), dtype=np.float64)
    # Just inside each cap, along the declared entry and exit directions.
    assert where(result, points[0] + np.array([0.0, 0.01, 0.0])) == TopAbs_IN
    assert where(result, points[-1] + np.array([0.0, 0.0, 0.01])) == TopAbs_IN
    assert where(result, points[0] - np.array([0.0, 0.01, 0.0])) == TopAbs_OUT
    assert where(result, points[-1] - np.array([0.0, 0.0, 0.01])) == TopAbs_OUT


def test_a_spline_may_continue_a_line_without_a_kink():
    document = loom(
        points=[[0.0, 90.0, -30.0], [70.0, 175.0, -40.0]],
        start_tangent=None,
        end_tangent=[0.0, 0.0, -1.0],
        lead=[0.0, 20.0, 0.0],
        profile=6,
    )
    result = brep(document)
    assert result.is_closed()
    assert sorted(result.surfaces()) == [
        "BSplineSurface",
        "Cylinder",
        "Plane",
        "Plane",
    ]
    start = np.array([0.0, 20.0, 0.0])
    points = [start, [0.0, 90.0, -30.0], [70.0, 175.0, -40.0]]
    length = 20.0 + hermite_length(
        points, incoming=(0.0, 1.0, 0.0), end_tangent=[0.0, 0.0, -1.0]
    )
    assert result.volume() == pytest.approx(tube_volume(2.0, length), rel=1e-6)


def test_the_loom_volume_does_not_follow_the_tessellation():
    coarse = brep(loom(path=2, profile=5), NEAR)
    fine = brep(loom(path=90, profile=256), NEAR)
    assert coarse.volume() == pytest.approx(fine.volume(), rel=1e-6)


def test_a_parameter_moves_the_loom_and_the_counts_mean_nothing_to_it():
    near = brep(loom(), NEAR)
    far = brep(loom(), {"head_x": 140.0, "head_y": 190.0, "head_z": -20.0})
    assert far.volume() != pytest.approx(near.volume(), rel=1e-3)


def test_a_spline_cusp_is_refused_as_the_mesh_refuses_it():
    document = loom(points=[[0.0, 40.0, 0.0], [0.0, 40.0, 0.0]])
    with pytest.raises(EvaluationError) as caught:
        brep(document)
    with pytest.raises(EvaluationError) as mesh:
        molejo.evaluate(document)
    assert str(caught.value) == str(mesh.value)


# --- the belt ---------------------------------------------------------------


def test_a_toothless_round_belt_is_cylinders_and_tori():
    # The delta spec's own scenario: a circle-profile wrap is analytic all
    # the way round, and says so with a zero tolerance.
    document = belt(circles=PULLEYS, path=4)
    document["profile"] = {"type": "circle", "radius": 0.6}
    document["tessellation"]["profile"] = 16
    result = brep(document)
    assert set(result.surfaces()) == {"Cylinder", "Torus"}
    assert result.tolerance == 0.0
    assert result.volume() == pytest.approx(
        tube_volume(0.6, loop_length(PULLEYS)), rel=1e-12
    )


def test_a_toothless_belt_prism_is_exact():
    result = brep(belt(circles=PULLEYS))
    assert set(result.surfaces()) == {"Plane", "Cylinder"}
    assert result.tolerance == 0.0
    assert result.volume() == pytest.approx(belt_volume(PULLEYS), rel=1e-12)


def test_a_toothed_belt_encloses_the_prism_between_its_traces():
    teeth = toothed(count=6, height=0.75)
    document = belt(circles=PULLEYS, teeth=teeth, phase=7.3)
    result = brep(document)
    assert result.volume() == pytest.approx(
        belt_volume(PULLEYS, teeth=teeth, origin=7.3), rel=1e-7
    )


def test_an_anchored_belt_puts_its_teeth_where_the_carriage_is():
    teeth = toothed(count=4, height=0.75)
    for carriage in (40.0, 170.0):
        document = belt(
            circles=CARRIAGE, teeth=teeth, anchor={"span": 0, "at": carriage}
        )
        result = brep(document)
        assert result.volume() == pytest.approx(
            belt_volume(CARRIAGE, teeth=teeth, origin=carriage), rel=1e-7
        )


def test_a_toothed_belt_keeps_its_crests_roots_and_flanks_exact():
    # Only the ramp that crosses an arc is approximated. Everything else --
    # the outer trace, the span flanks, the crest and root arcs, the two
    # faces of the band -- stays a plane or a cylinder.
    result = brep(belt(circles=PULLEYS, teeth=toothed(count=6), phase=7.3))
    surfaces = result.surfaces()
    assert set(surfaces) == {"Plane", "Cylinder", "SurfaceOfExtrusion"}
    assert sum(1 for name in surfaces if name in ANALYTIC) > len(surfaces) / 2


def test_a_ramp_that_crosses_an_arc_declares_its_tolerance():
    result = brep(belt(circles=PULLEYS, teeth=toothed(count=6), phase=7.3))
    assert result.tolerance == APPROXIMATION


def test_a_belt_whose_teeth_stay_on_its_spans_is_exact():
    # Two circles 210 apart, four teeth, and a phase that keeps every ramp
    # on a straight span: nothing spirals, so nothing is approximated and
    # the toothed belt is as exact as the toothless one.
    document = belt(circles=CARRIAGE, teeth=toothed(count=4), phase=45.0)
    result = brep(document)
    assert result.tolerance == 0.0
    assert set(result.surfaces()) <= ANALYTIC
    assert result.volume() == pytest.approx(
        belt_volume(CARRIAGE, teeth=toothed(count=4), origin=45.0), rel=1e-12
    )


def test_the_belt_volume_does_not_follow_the_tessellation():
    teeth = toothed(count=6)
    coarse = brep(belt(circles=PULLEYS, teeth=teeth, phase=7.3, path=3))
    fine = brep(belt(circles=PULLEYS, teeth=teeth, phase=7.3, path=90))
    assert coarse.volume() == pytest.approx(fine.volume(), rel=1e-12)


def test_a_toothed_belt_is_still_one_closed_solid():
    result = brep(belt(circles=PULLEYS, teeth=toothed(count=6), phase=7.3))
    assert result.is_closed()


# --- the loud boundary ------------------------------------------------------


def test_a_dangling_parameter_names_it_and_the_slot():
    document = cylinder()
    document["path"][0]["to"][2] = {"param": "length"}
    with pytest.raises(EvaluationError) as caught:
        brep(document, {})
    with pytest.raises(EvaluationError) as mesh:
        molejo.evaluate(document, {})
    assert str(caught.value) == str(mesh.value)
    assert "length" in str(caught.value)


@pytest.mark.parametrize("value", ["12", None, True, float("nan")])
def test_a_value_that_is_not_a_finite_number_is_refused(value):
    document = cylinder()
    document["path"][0]["to"][2] = {"param": "length"}
    with pytest.raises(EvaluationError) as caught:
        brep(document, {"length": value})
    with pytest.raises(EvaluationError) as mesh:
        molejo.evaluate(document, {"length": value})
    assert str(caught.value) == str(mesh.value)


@pytest.mark.parametrize(
    "mangle",
    [
        lambda d: d["path"][0].__setitem__("to", [0.0, 0.0, 0.0]),
        lambda d: d["profile"].__setitem__("radius", -1.0),
    ],
)
def test_a_geometric_refusal_reads_the_same_as_the_mesh_evaluators(mangle):
    document = cylinder()
    mangle(document)
    with pytest.raises(EvaluationError) as caught:
        brep(document)
    with pytest.raises(EvaluationError) as mesh:
        molejo.evaluate(document)
    assert str(caught.value) == str(mesh.value)


def test_a_wrap_refusal_reads_the_same_as_the_mesh_evaluators():
    document = belt(circles=[(0.0, 0.0, 8.0), (2.0, 0.0, 3.0)])
    with pytest.raises(EvaluationError) as caught:
        brep(document)
    with pytest.raises(EvaluationError) as mesh:
        molejo.evaluate(document)
    assert str(caught.value) == str(mesh.value)


def test_an_invalid_document_is_rejected_before_any_geometry():
    from molejo import SpecError

    document = cylinder()
    document["path"][0]["type"] = "squiggle"
    with pytest.raises(SpecError, match=r"path\[0\]"):
        brep(document)


def test_a_general_chain_may_not_close_yet():
    document = cylinder()
    document["loop"] = True
    with pytest.raises(NotImplementedError, match="loop"):
        brep(document)


def test_a_toothed_belt_needs_a_rectangular_section():
    # Teeth displace the profile's inner face along the loop, which the
    # prism construction can only extrude when the section is a rectangle.
    document = belt(
        circles=PULLEYS,
        section=[[-0.4, -3.0], [0.9, -1.0], [0.9, 3.0], [-0.4, 3.0]],
        teeth=toothed(count=6),
    )
    with pytest.raises(NotImplementedError, match="rectangul"):
        brep(document)


# --- the surface a consumer sees --------------------------------------------


def test_the_authoring_layer_evaluates_to_a_solid():
    shape = Shape(
        profile=Circle(radius=5.0),
        path=[Line(to=(0.0, 0.0, P.length))],
        path_samples=4,
        profile_samples=12,
    )
    result = shape.brep(length=12.0)
    assert result.volume() == pytest.approx(math.pi * 25.0 * 12.0, rel=1e-12)


def test_an_authored_belt_evaluates_like_its_document():
    shape = Shape(
        profile=Polygon(points=SECTION),
        path=[
            Wrap(
                around=[
                    {"center": (c[0], c[1]), "radius": c[2]} for c in PULLEYS
                ],
                teeth=Teeth(pitch=2.5, height=0.75, count=6),
                phase=P.travel,
            )
        ],
        path_samples=10,
        profile_samples=4,
        loop=True,
    )
    assert shape.brep(travel=7.3).volume() == pytest.approx(
        brep(shape.to_dict(), {"travel": 7.3}).volume(), rel=1e-15
    )


def test_the_result_states_its_size_and_its_tolerance():
    text = repr(brep(cylinder()))
    assert "BrepResult" in text and "tolerance" in text


def test_the_brep_surface_is_exported_from_the_package():
    assert molejo.brep.evaluate is not None
    assert issubclass(BrepError, Exception)


def test_a_zero_tolerance_result_carries_no_approximated_surface():
    # The guard behind the honesty claim: the evaluator refuses to declare
    # exactness it did not achieve.
    for document in (cylinder(), bend(), belt(circles=PULLEYS)):
        result = brep(document)
        if result.tolerance == 0.0:
            assert set(result.surfaces()) <= ANALYTIC
