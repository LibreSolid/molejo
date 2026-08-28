# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The belt: a wrap around circles, its teeth, and the closed loop.

The wrap is the first shape that comes back to where it started and the
first that is swept along something other than a circle, so this module
carries three settlements at once -- the wrap's own geometry, the
closed-loop join (no duplicate ring, no caps, ``V = R*M``), and what a
polygon profile means. All three are recorded in design.md under "The
wrap, its teeth, the polygon profile, and the closed loop", and every
assertion here is written against that record rather than against the
evaluator: the ring centres, the outward normals, the tooth modulation
and the whole vertex array are predicted here in closed form from the
circles alone.

The belt also admits an exact volume: because a wrap is planar and the
profile's local *y* is world +Z at every ring, a rectangular belt
section sweeps exactly the prism between its inner and outer traces,
whose volume is its width times the difference of two shoelace areas --
teeth included. That is the strongest independent check in the suite,
and it is why the fixtures use rectangular sections.
"""

import math

import numpy as np
import pytest

import molejo
from molejo import P, Polygon, Shape, Teeth, Wrap
from molejo.evaluator import EvaluationError, transport, Frame

# The same independent mesh arithmetic the earlier slices use; a second
# copy of it here could only drift from that one.
from test_evaluation import signed_volume, watertight_failures
from test_curved_paths import polygon_area, rings_of, sampled_volume

TAU = 2.0 * math.pi

#: A belt section: 1.3 thick, 6 wide, its inner face at x = -0.4, given
#: counter-clockwise in the profile frame as the winding convention asks.
SECTION = [[-0.4, -3.0], [0.9, -3.0], [0.9, 3.0], [-0.4, 3.0]]

#: Two 5.1 pitch-radius pulleys 210 apart: the Metamaquina2 belt.
CARRIAGE = [(0.0, 0.0, 5.1), (0.0, 210.0, 5.1)]

#: Three circles listed in the clockwise circulation their hull has.
PULLEYS = [(0.0, 0.0, 8.0), (30.0, 40.0, 3.0), (60.0, 0.0, 5.0)]


# --- the shapes under test -------------------------------------------------


def belt(
    circles=CARRIAGE,
    section=SECTION,
    teeth=None,
    anchor=None,
    phase=None,
    path=8,
    loop=True,
):
    """A wrap around ``circles``, its section swept as a closed loop."""
    wrap = {
        "type": "wrap",
        "around": [
            {"center": [circle[0], circle[1]], "radius": circle[2]}
            for circle in circles
        ],
    }
    if teeth is not None:
        wrap["teeth"] = teeth
    if anchor is not None:
        wrap["anchor"] = anchor
    if phase is not None:
        wrap["phase"] = phase
    return {
        "molejo": 1,
        "profile": {"type": "polygon", "points": [list(point) for point in section]},
        "path": [wrap],
        "loop": loop,
        "tessellation": {"path": path, "profile": len(section)},
    }


def toothed(count=8, height=0.75, pitch=2.5):
    return {"pitch": pitch, "height": height, "flank": "trapezoid", "count": count}


def bar(section, to=(0.0, 0.0, 10.0), path=3):
    """A polygon profile swept along one line: the polygon's own slice."""
    return {
        "molejo": 1,
        "profile": {"type": "polygon", "points": [list(point) for point in section]},
        "path": [{"type": "line", "to": list(to)}],
        "loop": False,
        "tessellation": {"path": path, "profile": len(section)},
    }


# --- independent closed forms ----------------------------------------------
#
# The wrap predicted from its circles alone, exactly as design.md pins it:
# the belt runs the external tangents, clockwise seen from +Z, touching
# every circle on its outward normal.


def rot90(vector):
    """``vector`` turned a quarter turn counter-clockwise."""
    return np.array([-vector[1], vector[0]])


def outward_normal(first, second):
    """The normal both circles are touched along by their common tangent."""
    span = np.array(second[:2]) - np.array(first[:2])
    length = float(np.linalg.norm(span))
    direction = span / length
    delta = (first[2] - second[2]) / length
    return delta * direction + math.sqrt(1.0 - delta * delta) * rot90(direction)


def elements(circles):
    """The wrap's 2k elements: span i, then the arc about circle i+1."""
    count = len(circles)
    normals = [
        outward_normal(circles[i], circles[(i + 1) % count]) for i in range(count)
    ]
    items = []
    for i in range(count):
        j = (i + 1) % count
        here, there = np.array(circles[i][:2]), np.array(circles[j][:2])
        normal = normals[i]
        start = here + circles[i][2] * normal
        end = there + circles[j][2] * normal
        items.append(
            {
                "kind": "span",
                "start": start,
                "end": end,
                "normal": normal,
                "length": float(np.linalg.norm(end - start)),
            }
        )
        arrival = math.atan2(normal[1], normal[0])
        departure = math.atan2(normals[j][1], normals[j][0])
        turn = (arrival - departure) % TAU
        items.append(
            {
                "kind": "arc",
                "centre": there,
                "radius": circles[j][2],
                "from": arrival,
                "turn": turn,
                "length": circles[j][2] * turn,
            }
        )
    return items


def loop_length(circles):
    return sum(item["length"] for item in elements(circles))


def wrap_rings(circles, segments):
    """Ring centres ``(R, 3)``, outward normals ``(R, 2)`` and stations ``(R,)``."""
    centres, normals, stations = [], [], []
    travelled = 0.0
    for item in elements(circles):
        for step in range(segments):
            fraction = step / segments
            if item["kind"] == "span":
                point = item["start"] + fraction * (item["end"] - item["start"])
                normal = item["normal"]
            else:
                angle = item["from"] - fraction * item["turn"]
                normal = np.array([math.cos(angle), math.sin(angle)])
                point = item["centre"] + item["radius"] * normal
            centres.append([point[0], point[1], 0.0])
            normals.append(normal)
            stations.append(travelled + fraction * item["length"])
        travelled += item["length"]
    return np.array(centres), np.array(normals), np.array(stations)


def modulation(station, origin, period):
    """The trapezoid: quarter crest on the origin, quarter ramp, quarter root."""
    fraction = ((station - origin) / period) % 1.0
    distance = min(fraction, 1.0 - fraction)
    return min(1.0, max(0.0, (0.375 - distance) * 4.0))


def displacements(circles, segments, teeth, origin=0.0):
    """How far each ring's inner face is pushed toward the circles."""
    _, _, stations = wrap_rings(circles, segments)
    period = loop_length(circles) / teeth["count"]
    return np.array(
        [teeth["height"] * modulation(station, origin, period) for station in stations]
    )


def belt_vertices(circles, section, segments, teeth=None, origin=0.0):
    """The whole wall vertex array, predicted from the circles alone."""
    centres, normals, _ = wrap_rings(circles, segments)
    points = np.asarray(section, dtype=np.float64)
    inner = points[:, 0] == points[:, 0].min()
    offsets = (
        displacements(circles, segments, teeth, origin)
        if teeth is not None
        else np.zeros(len(centres))
    )
    vertices = np.empty((len(centres), len(points), 3), dtype=np.float64)
    for ring in range(len(centres)):
        axis = np.array([normals[ring][0], normals[ring][1], 0.0])
        for j, (across, along) in enumerate(points):
            reach = across - (offsets[ring] if inner[j] else 0.0)
            vertices[ring, j] = centres[ring] + reach * axis + along * np.array(
                [0.0, 0.0, 1.0]
            )
    return vertices


def shoelace(points):
    """The signed area of a closed polygon, by the surveyor's formula."""
    points = np.asarray(points, dtype=np.float64)
    following = np.roll(points, -1, axis=0)
    return 0.5 * float(
        np.sum(points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1])
    )


def prism_between_traces(mesh, section, inner=0, outer=1):
    """The exact volume of the belt: width times inner-to-outer band area.

    A wrap is planar and the profile's local *y* is world +Z at every
    ring, so a rectangular section sweeps exactly a prism: the region
    between the trace of its inner face and the trace of its outer one,
    extruded by the section's width. Teeth are in the inner trace, so
    this is exact for a toothed belt too.
    """
    points = np.asarray(section, dtype=np.float64)
    width = points[:, 1].max() - points[:, 1].min()
    rings = rings_of(mesh, len(points))
    return width * (
        abs(shoelace(rings[:, outer, :2])) - abs(shoelace(rings[:, inner, :2]))
    )


def swept_volume(area, chords, tangents):
    """The volume a mitred sweep of a fixed cross-section describes.

    The closed form ``test_curved_paths.sampled_volume`` uses, with the
    area given rather than derived from a regular polygon; the suite
    checks the two agree where both apply.
    """
    turn = np.arccos(
        np.clip(np.einsum("ij,ij->i", tangents[:-1], tangents[1:]), -1.0, 1.0)
    )
    return float(np.sum(area * chords * np.cos(turn / 2.0)))


def test_the_local_volume_closed_form_is_the_shared_one():
    # `swept_volume` only generalizes `sampled_volume` to a section that
    # is not a regular polygon; on one that is, they must agree exactly.
    chords = np.full(4, 2.5)
    tangents = np.tile(np.array([0.0, 0.0, 1.0]), (5, 1))
    assert swept_volume(polygon_area(8, 1.5), chords, tangents) == pytest.approx(
        sampled_volume(8, 1.5, chords, tangents), rel=1e-15
    )


# --- the polygon profile, on its own ---------------------------------------


def test_a_polygon_profile_is_its_declared_points_in_order():
    section = [[0.0, 0.0], [4.0, 0.0], [4.0, 1.0], [1.0, 3.0]]
    mesh = molejo.evaluate(bar(section, path=2))
    rings = rings_of(mesh, 4)
    for ring in range(3):
        for j, (x, y) in enumerate(section):
            assert rings[ring, j] == pytest.approx((x, y, 5.0 * ring), abs=1e-12)


def test_a_polygon_prism_encloses_its_shoelace_volume_exactly():
    section = [[0.0, 0.0], [4.0, 0.0], [4.0, 1.0], [1.0, 3.0]]
    mesh = molejo.evaluate(bar(section, to=(0.0, 0.0, 10.0)))
    assert watertight_failures(mesh.faces) == []
    assert signed_volume(mesh) == pytest.approx(shoelace(section) * 10.0, rel=1e-12)


def test_a_polygon_point_may_be_bound_to_a_parameter():
    section = [[0.0, 0.0], [{"param": "wide"}, 0.0], [0.0, 2.0]]
    document = bar(section)
    thin = molejo.evaluate(document, {"wide": 1.0})
    fat = molejo.evaluate(document, {"wide": 5.0})
    assert thin.vertices.shape == fat.vertices.shape
    assert np.array_equal(thin.faces, fat.faces)
    assert signed_volume(fat) == pytest.approx(5.0 * signed_volume(thin), rel=1e-12)


def test_a_polygon_profile_carries_the_declared_counts():
    mesh = molejo.evaluate(bar([[0.0, 0.0], [2.0, 0.0], [0.0, 2.0]], path=4))
    assert mesh.vertices.shape == (5 * 3 + 2, 3)
    assert mesh.faces.shape == (2 * 4 * 3 + 2 * 3, 3)


# --- the counts of a closed loop -------------------------------------------


@pytest.mark.parametrize(
    "circles, segments",
    [(CARRIAGE, 8), (PULLEYS, 5), (PULLEYS, 12)],
    ids=["two-circles", "three-circles", "three-circles-finer"],
)
def test_a_wrap_is_two_elements_per_circle_and_no_caps(circles, segments):
    # 2k elements at N segments each, and a closed loop has no duplicate
    # ring and no cap centres: V = R*M exactly, F = 2*R*M.
    mesh = molejo.evaluate(belt(circles=circles, path=segments))
    rings = 2 * len(circles) * segments
    assert mesh.vertices.shape == (rings * 4, 3)
    assert mesh.faces.shape == (2 * rings * 4, 3)


def test_the_last_ring_wraps_onto_the_first():
    segments, profile = 6, 4
    mesh = molejo.evaluate(belt(path=segments))
    rings = 2 * len(CARRIAGE) * segments
    last = (rings - 1) * profile
    at = 2 * last
    assert mesh.faces[at].tolist() == [last, last + 1, 1]
    assert mesh.faces[at + 1].tolist() == [last, 1, 0]


def test_the_loop_leaves_no_duplicate_ring():
    mesh = molejo.evaluate(belt(path=8))
    centres = rings_of(mesh, 4).mean(axis=1)
    steps = np.linalg.norm(np.diff(np.vstack([centres, centres[:1]]), axis=0), axis=1)
    assert (steps > 1e-9).all(), "a duplicated ring would leave a zero step"


def test_a_closed_belt_is_watertight_and_winds_outward():
    for circles in (CARRIAGE, PULLEYS):
        mesh = molejo.evaluate(belt(circles=circles, path=7, teeth=toothed()))
        assert watertight_failures(mesh.faces) == [], circles
        assert signed_volume(mesh) > 0.0, circles


def test_neither_a_moving_idler_nor_a_phase_moves_a_vertex_index():
    document = belt(
        circles=[(0.0, 0.0, 8.0), (30.0, {"param": "idler"}, 3.0), (60.0, 0.0, 5.0)],
        teeth=toothed(),
        phase={"param": "travel"},
        path=6,
    )
    near = molejo.evaluate(document, {"idler": 40.0, "travel": 0.0})
    far = molejo.evaluate(document, {"idler": 52.0, "travel": 7.3})
    assert near.vertices.shape == far.vertices.shape
    assert np.array_equal(near.faces, far.faces)
    assert not np.array_equal(near.vertices, far.vertices)


# --- the wrap's geometry, ring by ring -------------------------------------


@pytest.mark.parametrize("circles", [CARRIAGE, PULLEYS], ids=["two", "three"])
def test_every_ring_sits_where_the_closed_form_says(circles):
    segments = 7
    mesh = molejo.evaluate(belt(circles=circles, path=segments))
    centres, _, _ = wrap_rings(circles, segments)
    assert rings_of(mesh, 4).mean(axis=1) == pytest.approx(centres, abs=1e-12)


@pytest.mark.parametrize("circles", [CARRIAGE, PULLEYS], ids=["two", "three"])
def test_every_wall_vertex_is_the_closed_form_vertex(circles):
    segments = 7
    mesh = molejo.evaluate(belt(circles=circles, path=segments))
    assert rings_of(mesh, 4) == pytest.approx(
        belt_vertices(circles, SECTION, segments), abs=1e-12
    )


def test_the_belt_starts_where_it_leaves_the_first_circle():
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=5))
    centre = rings_of(mesh, 4).mean(axis=1)[0]
    first = np.array(PULLEYS[0][:2]) + PULLEYS[0][2] * outward_normal(
        PULLEYS[0], PULLEYS[1]
    )
    assert centre == pytest.approx((first[0], first[1], 0.0), abs=1e-12)


def test_the_belt_rides_each_circle_at_its_pitch_radius():
    segments = 6
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=segments))
    centres = rings_of(mesh, 4).mean(axis=1)
    # Element 2i+1 is the arc about circle i+1: its rings sit at exactly
    # that circle's radius from its centre.
    for index in range(len(PULLEYS)):
        circle = PULLEYS[(index + 1) % len(PULLEYS)]
        arc = centres[(2 * index + 1) * segments : (2 * index + 2) * segments]
        radius = np.linalg.norm(arc[:, :2] - np.array(circle[:2]), axis=1)
        assert radius == pytest.approx(np.full(segments, circle[2]), abs=1e-12)


def test_every_span_is_tangent_to_the_two_circles_it_joins():
    segments = 6
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=segments))
    centres = rings_of(mesh, 4).mean(axis=1)
    for index in range(len(PULLEYS)):
        span = centres[2 * index * segments : (2 * index + 1) * segments]
        direction = span[-1] - span[0]
        direction = direction / np.linalg.norm(direction)
        for circle in (PULLEYS[index], PULLEYS[(index + 1) % len(PULLEYS)]):
            spoke = np.array([circle[0], circle[1], 0.0]) - span[0]
            across = spoke - float(np.dot(spoke, direction)) * direction
            assert float(np.linalg.norm(across)) == pytest.approx(circle[2], abs=1e-12)


def test_the_belt_lies_flat_in_the_world_plane():
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=5, teeth=toothed()))
    # The profile's local y is world +Z at every ring, exactly: a belt's
    # section takes exactly the two heights its points declare.
    heights = np.unique(mesh.vertices[:, 2])
    assert heights.tolist() == [-3.0, 3.0]


def test_the_belt_turns_clockwise_through_exactly_one_full_turn():
    segments = 9
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=segments))
    centres = rings_of(mesh, 4).mean(axis=1)[:, :2]
    chords = np.diff(np.vstack([centres, centres[:1]]), axis=0)
    angles = np.arctan2(chords[:, 1], chords[:, 0])
    turns = np.diff(np.concatenate([angles, angles[:1]]))
    turns = (turns + math.pi) % TAU - math.pi
    assert float(turns.sum()) == pytest.approx(-TAU, abs=1e-12)


def test_the_loop_length_is_the_closed_form_length():
    # Two equal circles: two external tangents plus two half turns.
    assert loop_length(CARRIAGE) == pytest.approx(
        2.0 * 210.0 + TAU * 5.1, rel=1e-12
    )
    segments = 64
    mesh = molejo.evaluate(belt(path=segments))
    centres = rings_of(mesh, 4).mean(axis=1)
    chords = np.linalg.norm(
        np.diff(np.vstack([centres, centres[:1]]), axis=0), axis=1
    )
    assert chords.sum() < loop_length(CARRIAGE), "a chord polyline cannot exceed its curve"
    assert chords.sum() == pytest.approx(loop_length(CARRIAGE), rel=1e-4)


def test_the_frame_comes_back_to_the_start_without_twist():
    # A wrap is planar, so every minimal rotation of the transport is
    # about +/-Z and the frame carried once round must return. Asserted,
    # not assumed: the closed loop depends on it.
    segments = 8
    circles = PULLEYS
    mesh = molejo.evaluate(belt(circles=circles, path=segments))
    rings = rings_of(mesh, 4)
    _, normals, _ = wrap_rings(circles, segments)

    # Ring 0's frame: outward normal and world +Z.
    start = np.array([normals[0][0], normals[0][1], 0.0])
    tangent = np.array([start[1], -start[0], 0.0])

    last = rings[-1].mean(axis=0)
    last_across = (rings[-1, 1] - rings[-1, 0])[:2]
    last_normal = np.array([last_across[0], last_across[1], 0.0])
    last_normal = last_normal / np.linalg.norm(last_normal)
    frame = Frame(
        origin=last,
        x=last_normal,
        y=(0.0, 0.0, 1.0),
        tangent=(last_normal[1], -last_normal[0], 0.0),
    )
    carried = transport(frame, tangent)
    assert carried.x == pytest.approx(start, abs=1e-12), "the belt came back twisted"
    assert carried.y == pytest.approx((0.0, 0.0, 1.0), abs=1e-12)


# --- teeth -----------------------------------------------------------------


def test_teeth_move_the_inner_face_and_nothing_else():
    segments = 8
    plain = molejo.evaluate(belt(circles=PULLEYS, path=segments))
    geared = molejo.evaluate(belt(circles=PULLEYS, path=segments, teeth=toothed()))
    smooth = rings_of(plain, 4)
    ridged = rings_of(geared, 4)
    # The section's outer vertices are points 1 and 2; the inner face is
    # every vertex at the minimum local x, here points 0 and 3.
    assert ridged[:, 1] == pytest.approx(smooth[:, 1], abs=1e-12)
    assert ridged[:, 2] == pytest.approx(smooth[:, 2], abs=1e-12)
    assert not np.allclose(ridged[:, 0], smooth[:, 0])
    # The two inner vertices move together: the face stays flat.
    assert (ridged[:, 0, :2]) == pytest.approx(ridged[:, 3, :2], abs=1e-12)


def test_the_tooth_pattern_is_the_declared_trapezoid():
    segments, teeth = 10, toothed(count=6, height=0.5)
    circles = PULLEYS
    mesh = molejo.evaluate(belt(circles=circles, path=segments, teeth=teeth))
    assert rings_of(mesh, 4) == pytest.approx(
        belt_vertices(circles, SECTION, segments, teeth=teeth), abs=1e-12
    )


def test_a_crest_sits_on_the_pattern_origin():
    # With no anchor and no phase the origin is the wrap's own origin, so
    # ring 0 must be a crest: displaced by the whole tooth height.
    segments, teeth = 12, toothed(count=4, height=0.5)
    plain = molejo.evaluate(belt(circles=PULLEYS, path=segments))
    geared = molejo.evaluate(belt(circles=PULLEYS, path=segments, teeth=teeth))
    moved = rings_of(plain, 4)[0, 0] - rings_of(geared, 4)[0, 0]
    assert float(np.linalg.norm(moved)) == pytest.approx(0.5, abs=1e-12)


def test_a_phase_of_one_whole_period_reproduces_the_belt():
    # The pattern is periodic in the loop, and the count is an integer
    # over it, so advancing by exactly one period changes nothing.
    segments, teeth = 8, toothed(count=6)
    period = loop_length(PULLEYS) / teeth["count"]
    document = belt(
        circles=PULLEYS, path=segments, teeth=teeth, phase={"param": "travel"}
    )
    here = molejo.evaluate(document, {"travel": 1.25})
    later = molejo.evaluate(document, {"travel": 1.25 + period})
    assert later.vertices == pytest.approx(here.vertices, abs=1e-9)


def test_a_phase_circulates_the_pattern_without_changing_counts():
    segments, teeth = 8, toothed(count=6)
    document = belt(
        circles=PULLEYS, path=segments, teeth=teeth, phase={"param": "travel"}
    )
    still = molejo.evaluate(document, {"travel": 0.0})
    running = molejo.evaluate(document, {"travel": 3.1})
    assert np.array_equal(still.faces, running.faces)
    assert still.vertices.shape == running.vertices.shape
    assert not np.array_equal(still.vertices, running.vertices)
    # The pattern moved along the belt, so the same vertex index is at a
    # different point of the tooth, but the loop encloses the same volume
    # to within the sampling.
    assert rings_of(running, 4) == pytest.approx(
        belt_vertices(
            PULLEYS, SECTION, segments, teeth=teeth, origin=3.1
        ),
        abs=1e-12,
    )


def test_an_anchor_puts_the_pattern_origin_on_its_span():
    # The clamp is at `at` along span 0, which begins at the wrap's own
    # origin, so the anchored pattern is the phase-shifted one.
    segments, teeth = 8, toothed(count=6)
    anchored = molejo.evaluate(
        belt(
            circles=PULLEYS,
            path=segments,
            teeth=teeth,
            anchor={"span": 0, "at": {"param": "y"}},
        ),
        {"y": 4.5},
    )
    assert rings_of(anchored, 4) == pytest.approx(
        belt_vertices(PULLEYS, SECTION, segments, teeth=teeth, origin=4.5), abs=1e-12
    )


def test_an_anchor_on_a_later_span_starts_from_that_span():
    segments, teeth = 8, toothed(count=6)
    items = elements(PULLEYS)
    start = sum(item["length"] for item in items[:2])
    mesh = molejo.evaluate(
        belt(
            circles=PULLEYS,
            path=segments,
            teeth=teeth,
            anchor={"span": 1, "at": 2.0},
        )
    )
    assert rings_of(mesh, 4) == pytest.approx(
        belt_vertices(PULLEYS, SECTION, segments, teeth=teeth, origin=start + 2.0),
        abs=1e-12,
    )


def test_the_carriage_carries_the_teeth_with_it():
    # The Metamaquina2 case: the belt is clamped to the carriage, so the
    # tooth at the clamp is the same tooth wherever the carriage is.
    segments, teeth = 12, toothed(count=8, height=0.75)
    document = belt(
        circles=CARRIAGE,
        path=segments,
        teeth=teeth,
        anchor={"span": 0, "at": {"param": "y"}},
    )
    period = loop_length(CARRIAGE) / teeth["count"]
    near = molejo.evaluate(document, {"y": 40.0})
    far = molejo.evaluate(document, {"y": 40.0 + period})
    assert far.vertices == pytest.approx(near.vertices, abs=1e-9)
    moved = molejo.evaluate(document, {"y": 40.0 + period / 2.0})
    assert not np.allclose(moved.vertices, near.vertices)


def test_a_moving_idler_changes_the_tooth_pitch_and_not_the_count():
    segments, teeth = 10, toothed(count=6, height=0.5)
    document = belt(
        circles=[(0.0, 0.0, 8.0), (30.0, {"param": "idler"}, 3.0), (60.0, 0.0, 5.0)],
        path=segments,
        teeth=teeth,
    )
    for idler in (40.0, 52.0):
        circles = [(0.0, 0.0, 8.0), (30.0, idler, 3.0), (60.0, 0.0, 5.0)]
        mesh = molejo.evaluate(document, {"idler": idler})
        assert rings_of(mesh, 4) == pytest.approx(
            belt_vertices(circles, SECTION, segments, teeth=teeth), abs=1e-12
        )
    # The two loops are different lengths, so the pitch length differs
    # while the tooth count does not.
    assert loop_length(
        [(0.0, 0.0, 8.0), (30.0, 40.0, 3.0), (60.0, 0.0, 5.0)]
    ) != pytest.approx(
        loop_length([(0.0, 0.0, 8.0), (30.0, 52.0, 3.0), (60.0, 0.0, 5.0)])
    )


def test_the_tooth_pattern_closes_at_the_seam():
    # An integer count over the loop is what makes the seam invisible:
    # the displacement the mesh actually carries steps no further from
    # the last ring to ring 0 than the ramp can rise in one sampling step.
    segments, teeth = 24, toothed(count=6, height=0.5)
    plain = rings_of(molejo.evaluate(belt(circles=PULLEYS, path=segments)), 4)
    geared = rings_of(
        molejo.evaluate(belt(circles=PULLEYS, path=segments, teeth=teeth)), 4
    )
    offsets = np.linalg.norm(plain[:, 0] - geared[:, 0], axis=1)
    period = loop_length(PULLEYS) / teeth["count"]
    step = loop_length(PULLEYS) / (2 * len(PULLEYS) * segments)
    # The ramp rises the whole height over a quarter period.
    slope = teeth["height"] / (0.25 * period)
    steps = np.abs(np.diff(np.concatenate([offsets, offsets[:1]])))
    assert (steps <= slope * step + 1e-12).all()


# --- what a belt encloses ---------------------------------------------------


def test_the_belt_encloses_the_prism_between_its_faces():
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=9))
    assert signed_volume(mesh) == pytest.approx(
        prism_between_traces(mesh, SECTION), rel=1e-12
    )


def test_a_toothed_belt_encloses_the_prism_its_teeth_leave():
    teeth = toothed(count=6, height=0.5)
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=12, teeth=teeth))
    assert signed_volume(mesh) == pytest.approx(
        prism_between_traces(mesh, SECTION), rel=1e-12
    )
    plain = molejo.evaluate(belt(circles=PULLEYS, path=12))
    assert signed_volume(mesh) > signed_volume(plain), "teeth add belt, not remove it"


def test_the_smooth_belt_is_the_sweep_its_sampling_describes():
    # The mitred-prism closed form the arc and the spring are held to,
    # read around a loop: R chords, and the analytic ring tangents on
    # either side of each of them.
    segments = 32
    mesh = molejo.evaluate(belt(circles=PULLEYS, path=segments))
    centres, normals, _ = wrap_rings(PULLEYS, segments)
    chords = np.linalg.norm(
        np.diff(np.vstack([centres, centres[:1]]), axis=0), axis=1
    )
    tangents = np.column_stack(
        [normals[:, 1], -normals[:, 0], np.zeros(len(normals))]
    )
    tangents = np.vstack([tangents, tangents[:1]])
    assert signed_volume(mesh) == pytest.approx(
        swept_volume(shoelace(SECTION), chords, tangents), rel=1e-3
    )


# --- authored belts ---------------------------------------------------------


def test_an_authored_belt_evaluates_like_its_document():
    shape = Shape(
        profile=Polygon(points=[tuple(point) for point in SECTION]),
        path=[
            Wrap(
                around=[
                    {"center": (0.0, 0.0), "radius": 5.1},
                    {"center": (0.0, 210.0), "radius": 5.1},
                ],
                teeth=Teeth(pitch=2.5, height=0.75, count=8),
                anchor={"span": 0, "at": P.y},
            )
        ],
        path_samples=12,
        profile_samples=4,
        loop=True,
    )
    authored = shape.evaluate(y=40.0)
    document = molejo.evaluate(
        belt(
            path=12,
            teeth=toothed(count=8, height=0.75),
            anchor={"span": 0, "at": {"param": "y"}},
        ),
        {"y": 40.0},
    )
    assert authored.vertices.tobytes() == document.vertices.tobytes()
    assert authored.faces.tobytes() == document.faces.tobytes()


def test_a_belt_evaluation_is_bitwise_repeatable():
    document = belt(teeth=toothed(), phase={"param": "travel"}, path=8)
    first = molejo.evaluate(document, {"travel": 3.25})
    second = molejo.evaluate(document, {"travel": 3.25})
    assert first.vertices.tobytes() == second.vertices.tobytes()


# --- degeneracies are refused, naming the slot -----------------------------


def test_a_circle_with_no_radius_is_refused():
    document = belt(circles=[(0.0, 0.0, {"param": "pulley"}), (0.0, 210.0, 5.1)])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {"pulley": 0.0})
    assert "path[0].around[0].radius" in str(caught.value)


def test_circles_too_close_for_an_external_tangent_are_refused():
    document = belt(circles=[(0.0, 0.0, 8.0), (0.0, {"param": "gap"}, 2.0)])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {"gap": 4.0})
    message = str(caught.value)
    assert "path[0].around[1]" in message
    assert "external tangent" in message


def test_two_circles_at_one_centre_are_refused():
    document = belt(circles=[(0.0, 0.0, 5.1), (0.0, 0.0, 5.1)])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document)
    assert "path[0].around[1]" in str(caught.value)


def test_a_negative_tooth_height_is_refused():
    document = belt(teeth={"pitch": 2.5, "height": {"param": "deep"}, "flank": "trapezoid", "count": 8})
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {"deep": -0.75})
    assert "path[0].teeth.height" in str(caught.value)


def test_a_dangling_parameter_in_a_circle_names_its_slot():
    document = belt(circles=[(0.0, 0.0, 5.1), ({"param": "x"}, 210.0, 5.1)])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    assert "path[0].around[1].center[0]" in str(caught.value)
    assert "x" in str(caught.value)


def test_a_dangling_parameter_in_the_anchor_names_its_slot():
    document = belt(teeth=toothed(), anchor={"span": 0, "at": {"param": "y"}})
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    assert "path[0].anchor.at" in str(caught.value)


# --- what this batch still does not evaluate -------------------------------


def test_a_looped_chain_that_is_not_a_wrap_is_still_not_evaluated():
    document = {
        "molejo": 1,
        "profile": {"type": "circle", "radius": 1.0},
        "path": [
            {"type": "line", "to": [10.0, 0.0, 0.0]},
            {"type": "line", "to": [10.0, 10.0, 0.0]},
            {"type": "line", "to": [0.0, 0.0, 0.0]},
        ],
        "loop": True,
        "tessellation": {"path": 2, "profile": 8},
    }
    with pytest.raises(NotImplementedError) as caught:
        molejo.evaluate(document)
    assert "loop" in str(caught.value)
    assert "wrap" in str(caught.value)
