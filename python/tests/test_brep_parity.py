# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The shared parity fixtures, run against the B-rep evaluator.

B-rep output carries no vertex contract -- there are no rings to number
and no faces to order -- so its parity with the two mesh evaluators is
property-based: for every fixture and every binding, the volume and the
area of the exact solid against the volume and the area of the fixture's
own expected mesh arrays.

Those two numbers are *not* meant to agree closely, and the fixture
format says so. A faceted mesh systematically underestimates the smooth
solid it samples: a circle profile of *M* vertices encloses
``(M/2pi) sin(2pi/M)`` of its circle, which is 4.5% short at *M* = 12 and
17% short at *M* = 6, and the path facets cut in from below as well. So a
fixture declares a `brep` property tolerance of its own, set from the
measured margin with about 30% of headroom, and the coordinate tolerances
the mesh suites use have nothing to do with this comparison.

What makes the loose tolerance worth asserting is the direction and the
company it keeps. The gap is one-sided -- the exact solid is always the
larger, never the smaller -- and the same solid is checked against an
independent closed form at 1e-6, which is five orders tighter than the
mesh could ever manage. Read together they say the thing worth saying:
the B-rep is not merely consistent with the facets, it is nearer truth
than they are, and by the amount faceting predicts.

The symmetry rule the mesh suites keep applies here too. Fixtures come
from the manifest, every fixture must declare a `brep` tolerance, and
every fixture must have a closed form in this module -- so a fixture
cannot be quietly skipped by being added without one.
"""

import copy
import math

import numpy as np
import pytest

pytest.importorskip("OCP", reason="the brep extra is not installed")

import molejo
import molejo.brep

from conftest import parity_files, parity_fixture, parity_manifest
from test_brep import belt_volume, hermite_length
from test_curved_paths import QUARTER, helix_length, tube_volume
from test_wrap import CARRIAGE

FILES = parity_files()


# --- the properties of an expected mesh -------------------------------------


def mesh_properties(vertices, faces):
    """The volume and area of a fixture's stored arrays, from the arrays.

    The divergence theorem over the triangles for the volume and the sum
    of their areas for the surface -- read off the expectation itself, so
    this compares the B-rep against what the fixture pins rather than
    against a second run of the mesh evaluator.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    triangles = vertices[faces]
    cross = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    volume = float(np.sum(np.einsum("ij,ij->i", triangles[:, 0], cross)) / 6.0)
    area = float(np.sum(np.linalg.norm(cross, axis=1)) / 2.0)
    return volume, area


# --- the closed form each fixture is checked against ------------------------
#
# One per fixture, written from design.md and from the fixture's own
# document. Nothing here borrows a line of either evaluator.


def _cylinder(values):
    return tube_volume(5.0, values["length"])


def _oblique_line(values):
    return tube_volume(2.5, math.sqrt(9.0 + 16.0 + values["rise"] ** 2))


def _quarter_bend(values):
    return tube_volume(1.5, 10.0 + 6.0 * QUARTER + (values["reach"] - 6.0))


def _spring(values):
    return tube_volume(1.0, helix_length(6.0, 2.5, values["height"]))


def _filament_loom(values):
    points = [
        [0.0, 0.0, 0.0],
        [0.0, 90.0, -35.0],
        [60.0, 170.0, -10.0],
        [values["head_x"], values["head_y"], values["head_z"]],
    ]
    length = hermite_length(
        points, start_tangent=[0.0, 1.0, 0.0], end_tangent=[0.0, 0.0, -1.0]
    )
    return tube_volume(2.0, length)


def _loom_lead_in(values):
    points = [
        [0.0, 20.0, 0.0],
        [0.0, 90.0, -30.0],
        [values["head_x"], 175.0, values["head_z"]],
    ]
    length = 20.0 + hermite_length(
        points, incoming=(0.0, 1.0, 0.0), end_tangent=[0.0, 0.0, -1.0]
    )
    return tube_volume(2.0, length)


def _carriage_belt(values):
    return belt_volume(
        CARRIAGE,
        teeth={"height": 0.75, "count": 4},
        origin=values["y"],
    )


def _three_pulley_belt(values):
    circles = [(0.0, 0.0, 8.0), (30.0, values["idler"], 3.0), (60.0, 0.0, 5.0)]
    return belt_volume(
        circles, teeth={"height": 0.75, "count": 6}, origin=values["travel"]
    )


def _reverse_bend_belt(values):
    # The middle circle carries a sense of -1: the belt is bent backwards
    # over it, so its neighbours are reached along internal tangents and
    # the teeth stand on the outer face.
    circles = [(0.0, 0.0, 8.0), (30.0, values["press"], 3.0, -1), (60.0, 0.0, 8.0)]
    return belt_volume(
        circles,
        teeth={"height": 0.75, "count": 6},
        origin=values["travel"],
        face="outer",
    )


#: The exact volume each fixture's document encloses, by hand. A fixture
#: without an entry fails the suite rather than being skipped.
CLOSED_FORMS = {
    "carriage-belt.json": _carriage_belt,
    "cylinder.json": _cylinder,
    "filament-loom.json": _filament_loom,
    "loom-lead-in.json": _loom_lead_in,
    "oblique-line.json": _oblique_line,
    "quarter-bend.json": _quarter_bend,
    "reverse-bend-belt.json": _reverse_bend_belt,
    "spring.json": _spring,
    "three-pulley-belt.json": _three_pulley_belt,
}

#: How close the B-rep must come to its closed form. Five orders inside
#: the loosest mesh comparison, and inside the declared approximation
#: tolerance for the constructions that carry one.
EXACTLY = 1e-6


# --- the comparison ---------------------------------------------------------


def compare(where, what, expected, actual, tolerance):
    """Raise ``AssertionError`` unless the two properties agree.

    Relative, because the fixtures range from a belt of thousands of cubic
    millimetres to a tube of a few hundred, and one-sided in its reporting
    so a failure says which way the departure ran.
    """
    departure = (actual - expected) / abs(expected)
    if abs(departure) > tolerance:
        raise AssertionError(
            f"{where}: B-rep {what} is {actual!r}, expected-mesh {what} is "
            f"{expected!r} (off by {departure:+.5f}, tolerance {tolerance:g})"
        )
    return departure


def run_fixture(filename, fixture):
    """Every case of one fixture, compared. Raises on the first departure."""
    tolerance = fixture["brep"]["tolerance"]
    for case in fixture["cases"]:
        result = molejo.brep.evaluate(fixture["spec"], case["values"])
        volume, area = mesh_properties(case["vertices"], fixture["faces"])
        where = f"{filename} [{case['name']}]"
        compare(where, "volume", volume, result.volume(), tolerance)
        compare(where, "area", area, result.area(), tolerance)


# --- the suite runs every fixture, or fails ---------------------------------


def test_the_manifest_and_the_directory_agree():
    assert sorted(parity_manifest()) == FILES


@pytest.mark.parametrize("filename", FILES)
def test_a_fixture_declares_a_brep_property_tolerance(filename):
    # The mesh suites' coordinate tolerances say nothing about this
    # comparison, so a fixture that has not measured its own faceting
    # margin cannot be run against the B-rep at all.
    fixture = parity_fixture(filename)
    assert "brep" in fixture, f"{filename} declares no brep property tolerance"
    assert set(fixture["brep"]) == {"tolerance"}
    tolerance = fixture["brep"]["tolerance"]
    assert 0.0 < tolerance < 1.0


def test_every_fixture_has_a_closed_form_here():
    # The symmetry rule: a fixture added to the manifest without a closed
    # form fails this suite instead of quietly running one assertion less.
    assert sorted(CLOSED_FORMS) == FILES


@pytest.mark.parametrize("filename", FILES)
def test_the_brep_agrees_with_the_expected_mesh(filename):
    run_fixture(filename, parity_fixture(filename))


@pytest.mark.parametrize("filename", FILES)
def test_the_brep_is_the_larger_of_the_two(filename):
    # A faceted mesh is inscribed in the smooth solid it samples, so it
    # can only understate its volume and its area. A B-rep that came out
    # smaller would mean the two are not the same shape.
    fixture = parity_fixture(filename)
    for case in fixture["cases"]:
        result = molejo.brep.evaluate(fixture["spec"], case["values"])
        volume, area = mesh_properties(case["vertices"], fixture["faces"])
        assert result.volume() > volume, case["name"]
        assert result.area() > area, case["name"]


@pytest.mark.parametrize("filename", FILES)
def test_the_brep_is_nearer_truth_than_the_facets(filename):
    # The other half of the loose tolerance's meaning. The same solid, the
    # same binding, against the closed form instead of against the
    # facets: five orders tighter, and the mesh's own gap is the faceting
    # deficit rather than a disagreement about the shape.
    fixture = parity_fixture(filename)
    for case in fixture["cases"]:
        result = molejo.brep.evaluate(fixture["spec"], case["values"])
        exact = CLOSED_FORMS[filename](case["values"])
        volume, _ = mesh_properties(case["vertices"], fixture["faces"])
        assert result.volume() == pytest.approx(exact, rel=EXACTLY), case["name"]
        assert abs(result.volume() - exact) < abs(volume - exact), case["name"]


@pytest.mark.parametrize("filename", FILES)
def test_a_fixtures_declared_tolerance_is_not_slack(filename):
    # Headroom, not licence: a tolerance an order above the measured
    # margin would stop catching anything.
    fixture = parity_fixture(filename)
    tolerance = fixture["brep"]["tolerance"]
    worst = 0.0
    for case in fixture["cases"]:
        result = molejo.brep.evaluate(fixture["spec"], case["values"])
        volume, area = mesh_properties(case["vertices"], fixture["faces"])
        worst = max(
            worst,
            abs(result.volume() - volume) / volume,
            abs(result.area() - area) / area,
        )
    assert worst < tolerance < 2.0 * worst


@pytest.mark.parametrize("filename", FILES)
def test_every_fixture_solid_is_closed(filename):
    fixture = parity_fixture(filename)
    for case in fixture["cases"]:
        assert molejo.brep.evaluate(fixture["spec"], case["values"]).is_closed()


# --- the comparison is held to account --------------------------------------


@pytest.mark.parametrize("filename", FILES)
def test_a_perturbed_expectation_fails_the_comparison(filename):
    # A comparator that compares nothing would pass every fixture above.
    perturbed = parity_fixture(filename)
    tolerance = perturbed["brep"]["tolerance"]
    for vertex in perturbed["cases"][0]["vertices"]:
        for axis in range(3):
            vertex[axis] *= 1.0 + 4.0 * tolerance
    with pytest.raises(AssertionError, match="volume"):
        run_fixture(filename, perturbed)


@pytest.mark.parametrize("filename", FILES)
def test_a_departure_inside_the_tolerance_still_passes(filename):
    # And a comparator that fails everything is no better.
    fixture = parity_fixture(filename)
    run_fixture(filename, copy.deepcopy(fixture))
