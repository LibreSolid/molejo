# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The loom: a spline through the designer's points, clamped at both ends.

The validation case is a 3D printer's filament run -- fixed at the
machine frame's entry with a fixed entry direction, clamped to the
extruder head whose position follows three parameters, sagging through a
waypoint or two in between. That case is what chose the flavour, and the
choice is recorded in design.md under "The spline, its end tangents, and
the loom": a chain of cubic Hermite spans through the declared points,
with uniform Catmull-Rom tangents inside and declared tangents at the
two ends.

Every assertion here is written against that record rather than against
the evaluator. A cubic Hermite is small enough to reproduce in full --
the tangents, the basis, the velocity -- so this module predicts the ring
centres and the analytic tangents from the document alone, and a
deliberately planar loom is predicted all the way down to the vertex,
because a curve whose tangents stay in one plane has a frame that closed
form can reach.

The loom is also where the K^d claim stops being rhetoric. A shape
following three axes at once is exactly what a sampled representation
cannot serve, and what molejo asserts instead is structural: every
numeric slot is read once per evaluation, and a fully-parametric loom
and its fully-literal twin do the identical arithmetic. That is a
property of the code, not a timing, so it is tested as one.
"""

import math

import numpy as np
import pytest

import molejo
import molejo.evaluator
from molejo import Circle, Line, P, Shape, Spline
from molejo.evaluator import EvaluationError

# The same independent mesh arithmetic the earlier slices use; a second
# copy of it here could only drift from that one.
from test_evaluation import signed_volume, watertight_failures
from test_curved_paths import polygon_area, profile_offsets, rings_of
from test_wrap import swept_volume

#: Where the filament leaves the frame's entry fitting: along +Y, the
#: direction the bulkhead points.
ENTRY = [0.0, 1.0, 0.0]

#: How the filament enters the extruder: from above, going down, however
#: the head is standing.
INTO_THE_HEAD = [0.0, 0.0, -1.0]

#: The run: out of the frame, sagging to -35, back up over the gantry
#: rail, then down into the head. The head is the parametric one.
SAG = [[0.0, 90.0, -35.0], [60.0, 170.0, -10.0]]
HEAD = [{"param": "head_x"}, {"param": "head_y"}, {"param": "head_z"}]

NEAR = {"head_x": 95.0, "head_y": 215.0, "head_z": -45.0}
FAR = {"head_x": 140.0, "head_y": 190.0, "head_z": -20.0}


# --- the shapes under test -------------------------------------------------


def loom(
    points=None,
    start_tangent=ENTRY,
    end_tangent=INTO_THE_HEAD,
    lead=None,
    tube=2.0,
    path=6,
    profile=8,
):
    """A tube of radius ``tube`` swept along a spline, with an optional
    straight lead-in before it."""
    primitive = {
        "type": "spline",
        "points": [list(point) for point in (SAG + [HEAD] if points is None else points)],
    }
    if start_tangent is not None:
        primitive["start_tangent"] = list(start_tangent)
    if end_tangent is not None:
        primitive["end_tangent"] = list(end_tangent)
    chain = [] if lead is None else [{"type": "line", "to": list(lead)}]
    return {
        "molejo": 1,
        "profile": {"type": "circle", "radius": tube},
        "path": chain + [primitive],
        "loop": False,
        "tessellation": {"path": path, "profile": profile},
    }


def bound(points, values):
    """A points list with its parameter references replaced by numbers."""
    return [
        [values[slot["param"]] if isinstance(slot, dict) else slot for slot in point]
        for point in points
    ]


# --- independent closed forms ----------------------------------------------
#
# The spline predicted from its document alone, exactly as design.md pins
# it: Hermite spans through P0 (the point the path has reached) and the
# declared points, Catmull-Rom tangents inside, clamped ends.


def unit(vector):
    vector = np.asarray(vector, dtype=np.float64)
    return vector / np.linalg.norm(vector)


def hermite_tangents(points, start_tangent=None, end_tangent=None, incoming=(0.0, 0.0, 1.0)):
    """``m_0 … m_n``, the tangent the curve carries at each point.

    ``points`` includes the start ``P_0`` the path handed over. A declared
    tangent is a direction: its length is ignored and the speed comes
    from the adjacent chord, which is the scale the Catmull-Rom interior
    tangents carry.
    """
    p = np.asarray(points, dtype=np.float64)
    n = len(p) - 1
    m = np.zeros((n + 1, 3), dtype=np.float64)
    for i in range(1, n):
        m[i] = 0.5 * (p[i + 1] - p[i - 1])
    start = unit(incoming if start_tangent is None else start_tangent)
    m[0] = float(np.linalg.norm(p[1] - p[0])) * start
    if end_tangent is None:
        m[n] = p[n] - p[n - 1]
    else:
        m[n] = float(np.linalg.norm(p[n] - p[n - 1])) * unit(end_tangent)
    return m


def hermite_rings(points, segments, **kwargs):
    """Ring centres ``(R, 3)`` and unit tangents ``(R, 3)``, ``R = n*N + 1``.

    Segments are spent per span, and a joint's ring belongs to the span
    that leaves it, so the last span alone contributes its final ring.
    """
    p = np.asarray(points, dtype=np.float64)
    n = len(p) - 1
    m = hermite_tangents(points, **kwargs)
    centres, tangents = [], []
    for i in range(n):
        rings = segments + 1 if i == n - 1 else segments
        for j in range(rings):
            t = j / segments
            centres.append(
                (2 * t**3 - 3 * t**2 + 1) * p[i]
                + (t**3 - 2 * t**2 + t) * m[i]
                + (3 * t**2 - 2 * t**3) * p[i + 1]
                + (t**3 - t**2) * m[i + 1]
            )
            velocity = (
                (6 * t**2 - 6 * t) * (p[i] - p[i + 1])
                + (3 * t**2 - 4 * t + 1) * m[i]
                + (3 * t**2 - 2 * t) * m[i + 1]
            )
            tangents.append(unit(velocity))
    return np.array(centres), np.array(tangents)


def loom_points(values, points=None, start=(0.0, 0.0, 0.0)):
    """``P_0 … P_n``: where the path had reached, then the declared points."""
    declared = SAG + [HEAD] if points is None else points
    return [list(start)] + bound(declared, values)


def sampled_centres(mesh, profile):
    return rings_of(mesh, profile).mean(axis=1)


# --- how a spline is counted -----------------------------------------------


def test_a_spline_spends_the_declared_segments_on_every_span():
    # Three declared points are three spans at 6 segments each: 18
    # segments, 19 rings, and the two cap centres an open sweep ends with.
    mesh = molejo.evaluate(loom(path=6, profile=8), NEAR)
    assert mesh.vertices.shape == (19 * 8 + 2, 3)
    assert mesh.faces.shape == (2 * 18 * 8 + 2 * 8, 3)


def test_one_span_is_still_n_plus_one_rings():
    # A spline of a single declared point is the per-primitive rule the
    # cylinder pinned, read through the per-span one.
    mesh = molejo.evaluate(loom(points=[HEAD], path=6, profile=8), NEAR)
    assert mesh.vertices.shape == (7 * 8 + 2, 3)


def test_the_ring_count_does_not_follow_a_parameter():
    document = loom(path=5, profile=6)
    near = molejo.evaluate(document, NEAR)
    far = molejo.evaluate(document, FAR)
    assert near.vertices.shape == far.vertices.shape
    assert np.array_equal(near.faces, far.faces)
    assert not np.array_equal(near.vertices, far.vertices)


def test_a_spline_in_a_chain_spends_its_segments_per_span():
    # A line lead-in at 5 segments contributes 5 rings (its last is the
    # joint, owned by the spline), then three spans at 5 each: 21 rings.
    mesh = molejo.evaluate(loom(lead=[0.0, 20.0, 0.0], path=5, profile=6), NEAR)
    assert sampled_centres(mesh, 6).shape == (21, 3)


# --- the loom, ring by ring ------------------------------------------------


@pytest.mark.parametrize("values", [NEAR, FAR], ids=["near", "far"])
def test_every_ring_sits_where_the_closed_form_says(values):
    segments, profile = 6, 8
    mesh = molejo.evaluate(loom(path=segments, profile=profile), values)
    centres, _ = hermite_rings(
        loom_points(values), segments, start_tangent=ENTRY, end_tangent=INTO_THE_HEAD
    )
    assert sampled_centres(mesh, profile) == pytest.approx(centres, abs=1e-12)


@pytest.mark.parametrize("values", [NEAR, FAR], ids=["near", "far"])
def test_both_ends_are_hit_exactly(values):
    # Not within a tolerance: the Hermite basis is exactly (1, 0, 0, 0) at
    # t = 0 and exactly (0, 0, 1, 0) at t = 1, so an endpoint is the
    # declared point itself, bit for bit. A loom clamped to a moving head
    # that only nearly reached it would be a different promise. The two
    # cap centres are the mesh's own record of those two ring centres.
    mesh = molejo.evaluate(loom(path=6, profile=8), values)
    assert mesh.vertices[-2].tolist() == [0.0, 0.0, 0.0]
    assert mesh.vertices[-1].tolist() == [
        values["head_x"], values["head_y"], values["head_z"]
    ]


def test_every_waypoint_is_hit_exactly():
    # The whole reason the flavour interpolates: a sag point the designer
    # placed is a point the curve passes through, not a handle near it.
    # A wall ring carries no centre of its own, so this reads it back as
    # the mean of the ring's vertices, whose residual is float noise --
    # 1e-12 against coordinates of a couple of hundred.
    segments, profile = 6, 8
    mesh = molejo.evaluate(loom(path=segments, profile=profile), NEAR)
    centres = sampled_centres(mesh, profile)
    for index, point in enumerate(SAG):
        assert centres[(index + 1) * segments] == pytest.approx(point, abs=1e-12)


def test_the_end_tangents_are_the_declared_directions():
    # A ring lies across the local tangent, so the first and last rings
    # are the mesh's own statement of where the curve leaves and where it
    # arrives -- exactly, not within a chord's error.
    segments, profile, tube = 8, 12, 2.0
    mesh = molejo.evaluate(loom(tube=tube, path=segments, profile=profile), NEAR)
    rings = rings_of(mesh, profile)
    spokes = rings - rings.mean(axis=1)[:, None, :]
    assert spokes[0] @ unit(ENTRY) == pytest.approx(np.zeros(profile), abs=1e-12)
    assert spokes[-1] @ unit(INTO_THE_HEAD) == pytest.approx(np.zeros(profile), abs=1e-12)

    _, tangents = hermite_rings(
        loom_points(NEAR), segments, start_tangent=ENTRY, end_tangent=INTO_THE_HEAD
    )
    assert tangents[0] == pytest.approx(unit(ENTRY), abs=1e-15)
    assert tangents[-1] == pytest.approx(unit(INTO_THE_HEAD), abs=1e-15)


def test_a_declared_tangent_is_a_direction_and_its_length_is_ignored():
    # As `arc.axis` is: what the author declares is where the curve
    # points, and the speed comes from the adjacent chord.
    plain = molejo.evaluate(loom(start_tangent=[0.0, 1.0, 0.0]), NEAR)
    stretched = molejo.evaluate(loom(start_tangent=[0.0, 37.5, 0.0]), NEAR)
    assert stretched.vertices == pytest.approx(plain.vertices, abs=1e-12)


def test_the_curve_is_c1_across_every_interior_point():
    # The point of a Hermite chain: consecutive spans share the tangent
    # vector at the point between them, so no author has to arrange it.
    # Two claims, and neither alone would do. The ring at a joint lies
    # across the shared analytic tangent, exactly; and the apparent kink
    # the chords leave there is the sampling's own error, so it falls with
    # the step -- which a real kink would not do.
    profile = 8
    points = loom_points(NEAR)
    m = hermite_tangents(points, start_tangent=ENTRY, end_tangent=INTO_THE_HEAD)
    kinks = {}
    for segments in (16, 32):
        mesh = molejo.evaluate(loom(path=segments, profile=profile), NEAR)
        rings = rings_of(mesh, profile)
        centres = rings.mean(axis=1)
        spokes = rings - centres[:, None, :]
        angles = []
        for joint in range(1, len(points) - 1):
            ring = joint * segments
            assert spokes[ring] @ unit(m[joint]) == pytest.approx(
                np.zeros(profile), abs=1e-12
            ), joint
            before = unit(centres[ring] - centres[ring - 1])
            after = unit(centres[ring + 1] - centres[ring])
            angles.append(math.acos(min(1.0, float(np.dot(before, after)))))
        kinks[segments] = np.array(angles)

    assert (kinks[32] <= 0.6 * kinks[16]).all(), "a real kink would not shrink"
    # What is left is the turn one chord of this run makes, some four
    # degrees at its sharpest joint, not a discontinuity.
    assert (kinks[32] < 0.1).all()


def test_every_ring_is_a_circle_perpendicular_to_the_analytic_tangent():
    segments, profile, tube = 12, 16, 2.0
    mesh = molejo.evaluate(loom(tube=tube, path=segments, profile=profile), NEAR)
    rings = rings_of(mesh, profile)
    spokes = rings - rings.mean(axis=1)[:, None, :]

    assert np.linalg.norm(spokes, axis=2) == pytest.approx(
        np.full(spokes.shape[:2], tube), abs=1e-12
    ), "the tube's cross-section stayed a circle"

    _, tangents = hermite_rings(
        loom_points(NEAR), segments, start_tangent=ENTRY, end_tangent=INTO_THE_HEAD
    )
    assert np.einsum("ijk,ik->ij", spokes, tangents) == pytest.approx(
        np.zeros(spokes.shape[:2]), abs=1e-12
    ), "no shear: every ring lies across the local tangent"


def test_a_planar_loom_is_predicted_all_the_way_down_to_the_vertex():
    # Every tangent of this run stays in the world XZ plane, so every
    # minimal rotation of the transport is about +/-Y: the profile's y is
    # exactly world +Y and its x is the tangent turned a quarter turn.
    # That makes the whole vertex array reachable in closed form, which
    # the general 3D loom's composed frame is not.
    segments, profile, tube = 8, 12, 2.0
    points = [[0.0, 0.0, 40.0], [60.0, 0.0, 70.0], [90.0, 0.0, 30.0]]
    document = loom(
        points=points,
        start_tangent=[0.0, 0.0, 1.0],
        end_tangent=[0.0, 0.0, -1.0],
        tube=tube,
        path=segments,
        profile=profile,
    )
    mesh = molejo.evaluate(document, {})

    centres, tangents = hermite_rings(
        [[0.0, 0.0, 0.0]] + points,
        segments,
        start_tangent=[0.0, 0.0, 1.0],
        end_tangent=[0.0, 0.0, -1.0],
    )
    turn = np.arctan2(tangents[:, 0], tangents[:, 2])
    x = np.column_stack([np.cos(turn), np.zeros(len(turn)), -np.sin(turn)])
    y = np.tile(np.array([0.0, 1.0, 0.0]), (len(turn), 1))
    offsets = profile_offsets(profile, tube)
    expected = (
        centres[:, None, :]
        + offsets[None, :, 0, None] * x[:, None, :]
        + offsets[None, :, 1, None] * y[:, None, :]
    )
    assert rings_of(mesh, profile) == pytest.approx(expected, abs=1e-12)
    # And the two cap centres are the path's own ends.
    assert mesh.vertices[-2] == pytest.approx(centres[0], abs=1e-12)
    assert mesh.vertices[-1] == pytest.approx(centres[-1], abs=1e-12)


def test_the_loom_is_watertight_and_winds_outward():
    for values in (NEAR, FAR):
        mesh = molejo.evaluate(loom(path=9, profile=16), values)
        assert watertight_failures(mesh.faces) == [], values
        assert signed_volume(mesh) > 0.0, values


def test_the_loom_encloses_the_tube_the_sampling_describes():
    # The mitred-prism closed form the arc and the spring are held to,
    # read along a spline: R-1 chords, and the analytic ring tangents on
    # either side of each of them.
    segments, profile, tube = 48, 24, 2.0
    mesh = molejo.evaluate(loom(tube=tube, path=segments, profile=profile), NEAR)
    centres, tangents = hermite_rings(
        loom_points(NEAR), segments, start_tangent=ENTRY, end_tangent=INTO_THE_HEAD
    )
    chords = np.linalg.norm(np.diff(centres, axis=0), axis=1)
    assert signed_volume(mesh) == pytest.approx(
        swept_volume(polygon_area(profile, tube), chords, tangents), rel=1e-4
    )


# --- the defaults, which no literal could state ----------------------------


def test_without_a_start_tangent_a_spline_leaves_the_way_it_came():
    # The chain rule made a default: a lead-in line hands over its
    # direction, so the joint is C1 and the frame crosses it unturned --
    # which a document could not say literally when the lead-in is bound
    # to a parameter.
    segments, profile = 6, 8
    mesh = molejo.evaluate(
        loom(lead=[0.0, 20.0, 0.0], start_tangent=None, path=segments, profile=profile),
        NEAR,
    )
    rings = rings_of(mesh, profile)
    centres = rings.mean(axis=1)

    # The joint ring belongs to the spline, and it lies across the line's
    # own direction: the spline left the way it came.
    assert rings[segments][:, 1] == pytest.approx(np.full(profile, 20.0), abs=1e-12)
    # No twist either: the frame carried across a tangent-continuous joint
    # is the identity, so the two rings' profiles are parallel.
    assert (rings[segments] - centres[segments]) == pytest.approx(
        rings[segments - 1] - centres[segments - 1], abs=1e-12
    )


def test_a_lone_spline_without_a_start_tangent_leaves_along_the_start_frame():
    segments, profile = 8, 8
    points = [[0.0, 0.0, 60.0], [40.0, 0.0, 90.0]]
    mesh = molejo.evaluate(
        loom(points=points, start_tangent=None, end_tangent=None,
             path=segments, profile=profile),
        {},
    )
    # The start frame's tangent is +Z, so ring 0 lies in the world's own
    # XY plane -- the whole ring at z = 0.
    assert rings_of(mesh, profile)[0][:, 2] == pytest.approx(
        np.zeros(profile), abs=1e-12
    )


def test_without_an_end_tangent_a_spline_arrives_along_its_final_chord():
    segments, profile = 6, 8
    mesh = molejo.evaluate(loom(end_tangent=None, path=segments, profile=profile), NEAR)
    centres, tangents = hermite_rings(
        loom_points(NEAR), segments, start_tangent=ENTRY, end_tangent=None
    )
    assert sampled_centres(mesh, profile) == pytest.approx(centres, abs=1e-12)

    points = loom_points(NEAR)
    chord = unit(np.array(points[-1]) - np.array(points[-2]))
    assert tangents[-1] == pytest.approx(chord, abs=1e-15)


def test_a_spline_hands_its_end_frame_to_the_primitive_after_it():
    segments, profile = 6, 8
    document = loom(path=segments, profile=profile)
    document["path"].append({"type": "line", "to": [120.0, 260.0, -80.0]})
    mesh = molejo.evaluate(document, NEAR)
    centres = sampled_centres(mesh, profile)
    assert len(centres) == 3 * segments + segments + 1
    # The line starts where the spline ended: no primitive says where it
    # starts, so the joint is shared and sampled once.
    assert centres[3 * segments] == pytest.approx(
        [NEAR["head_x"], NEAR["head_y"], NEAR["head_z"]], abs=1e-12
    )
    assert mesh.vertices[-1].tolist() == [120.0, 260.0, -80.0]
    assert watertight_failures(mesh.faces) == []


# --- the K^d claim, asserted structurally ----------------------------------


def slot_reads(document, values, monkeypatch):
    """Every numeric slot the evaluation reads, in the order it reads them."""
    read = []
    original = molejo.evaluator._resolve

    def counting(slot, bindings, loc):
        read.append(loc)
        return original(slot, bindings, loc)

    monkeypatch.setattr(molejo.evaluator, "_resolve", counting)
    molejo.evaluate(document, values)
    monkeypatch.undo()
    return read


def test_a_parametric_loom_costs_exactly_what_its_literal_twin_costs(monkeypatch):
    # The K^d claim, made structural: a sampled representation would owe a
    # grid over the three head axes, and molejo owes one evaluation. So
    # the fully-literal loom and the fully-parametric one must do the same
    # arithmetic -- the same slots, in the same order, to the same bits --
    # and nothing may vary but where the numbers came from.
    parametric = loom(path=6, profile=8)
    literal = loom(points=SAG + bound([HEAD], NEAR), path=6, profile=8)

    bound_reads = slot_reads(parametric, NEAR, monkeypatch)
    literal_reads = slot_reads(literal, {}, monkeypatch)
    assert bound_reads == literal_reads

    assert molejo.evaluate(literal, {}).vertices.tobytes() == (
        molejo.evaluate(parametric, NEAR).vertices.tobytes()
    )


def test_every_numeric_slot_is_read_exactly_once(monkeypatch):
    # Nothing anywhere samples a parameter grid: there is one read per
    # slot in the document, so evaluation cost follows the declared
    # tessellation and the document's size, never the parameter count.
    document = loom(path=6, profile=8)
    read = slot_reads(document, NEAR, monkeypatch)
    # One radius, three points of three, two tangents of three.
    assert len(read) == 1 + 3 * 3 + 2 * 3
    assert len(set(read)) == len(read)


@pytest.mark.parametrize("count", [0, 1, 3], ids=["none", "one", "three"])
def test_the_slot_count_does_not_move_with_the_parameter_count(monkeypatch, count):
    names = ["head_x", "head_y", "head_z"]
    head = [
        {"param": names[axis]} if axis < count else [95.0, 215.0, -45.0][axis]
        for axis in range(3)
    ]
    document = loom(points=SAG + [head], path=6, profile=8)
    values = {name: NEAR[name] for name in names[:count]}
    assert len(slot_reads(document, values, monkeypatch)) == 1 + 3 * 3 + 2 * 3


# --- authored looms --------------------------------------------------------


def test_an_authored_loom_evaluates_like_its_document():
    shape = Shape(
        profile=Circle(radius=2.0),
        path=[
            Line(to=(0.0, 20.0, 0.0)),
            Spline(
                points=[(0.0, 90.0, -35.0), (60.0, 170.0, -10.0),
                        (P.head_x, P.head_y, P.head_z)],
                end_tangent=(0.0, 0.0, -1.0),
            ),
        ],
        path_samples=6,
        profile_samples=8,
    )
    authored = shape.evaluate(**NEAR)
    document = molejo.evaluate(
        loom(lead=[0.0, 20.0, 0.0], start_tangent=None, path=6, profile=8), NEAR
    )
    assert authored.vertices.tobytes() == document.vertices.tobytes()
    assert authored.faces.tobytes() == document.faces.tobytes()


def test_an_authored_spline_names_the_parameters_it_binds():
    shape = Shape(
        profile=Circle(radius=2.0),
        path=[Spline(points=[(P.head_x, P.head_y, P.head_z)], start_tangent=(0.0, 1.0, 0.0))],
        path_samples=6,
        profile_samples=8,
    )
    assert shape.params == frozenset({"head_x", "head_y", "head_z"})


def test_a_loom_evaluation_is_bitwise_repeatable():
    document = loom(path=6, profile=8)
    first = molejo.evaluate(document, NEAR)
    second = molejo.evaluate(document, NEAR)
    assert first.vertices.tobytes() == second.vertices.tobytes()


# --- degeneracies are refused, naming the slot -----------------------------


def test_a_point_coinciding_with_the_one_before_it_is_refused():
    document = loom(points=[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    assert "path[0].points[0]" in str(caught.value)


def test_a_repeated_waypoint_is_refused_naming_the_later_one():
    document = loom(points=[[0.0, 40.0, 0.0], [0.0, 40.0, 0.0], [0.0, 90.0, 0.0]])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    assert "path[0].points[1]" in str(caught.value)


def test_a_start_tangent_with_no_direction_is_refused():
    document = loom(start_tangent=[0.0, {"param": "aim"}, 0.0])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, dict(NEAR, aim=0.0))
    assert "path[0].start_tangent" in str(caught.value)


def test_an_end_tangent_with_no_direction_is_refused():
    document = loom(end_tangent=[0.0, 0.0, 0.0])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, NEAR)
    assert "path[0].end_tangent" in str(caught.value)


def test_a_point_whose_neighbours_coincide_is_refused():
    # The run doubles back on itself, so the Catmull-Rom tangent at the
    # middle point vanishes and the curve has no direction there.
    document = loom(
        points=[[0.0, 40.0, 0.0], [0.0, 0.0, 0.0], [0.0, 60.0, 0.0]],
        start_tangent=[0.0, 1.0, 0.0],
        end_tangent=[0.0, 1.0, 0.0],
    )
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    assert "path[0].points[0]" in str(caught.value)


def test_a_dangling_parameter_in_a_spline_point_names_its_slot():
    document = loom(path=6, profile=8)
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {"head_x": 95.0, "head_y": 215.0})
    assert "path[0].points[2][2]" in str(caught.value)
    assert "head_z" in str(caught.value)


def test_a_dangling_parameter_in_a_tangent_names_its_slot():
    document = loom(end_tangent=[0.0, 0.0, {"param": "aim"}])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, NEAR)
    assert "path[0].end_tangent[2]" in str(caught.value)
    assert "aim" in str(caught.value)


def test_a_degenerate_spline_in_a_chain_names_its_own_position():
    document = loom(points=[[0.0, 0.0, 20.0], [10.0, 0.0, 20.0]], lead=[0.0, 0.0, 20.0])
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    assert "path[1].points[0]" in str(caught.value)
