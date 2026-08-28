# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The curved primitives, and the chains the first slice could not make.

`arc` and `helix` are the second and third things a path can do, and
between them they force three conventions the cylinder never had to
answer: how `tessellation.path` is spent on a path of several
primitives, which primitive owns the ring at a joint, and how the
profile frame is carried along a curve that is turning under it. All
three are recorded in design.md under "Chained paths, arcs, and
helices", and every assertion here is written against that record
rather than against the evaluator.

The quarter bend is deliberately checkable in closed form all the way
down to the vertex: a line up +Z, a quarter turn toward +X about +Y,
then a line along +X. Its arc turns about a fixed axis, so the
rotation-minimizing frame is a plain rotation about that same axis, and
the whole mesh can be predicted here without borrowing a line of the
evaluator's arithmetic. The helix cannot be predicted that way -- its
frame is genuinely the composition of N rotations -- so it is held to
the invariants that matter instead: rings on the analytic curve, rings
perpendicular to the analytic tangent, a cross-section that is still a
circle of the wire's radius, and a coil count that does not move when
the pitch does.
"""

import math

import numpy as np
import pytest

import molejo
from molejo import Arc, Circle, Helix, Line, P, Shape
from molejo.evaluator import EvaluationError, START_FRAME, transport

# The same independent mesh arithmetic the cylinder slice uses; a second
# copy of it here could only drift from that one.
from test_evaluation import chord_deficit, signed_volume, watertight_failures

QUARTER = math.pi / 2.0


# --- the shapes under test -------------------------------------------------


def bend(reach=20.0, wire=1.5, radius=6.0, rise=10.0, path=4, profile=8):
    """A quarter-bend tube: line up +Z, a quarter turn, a line along +X."""
    return {
        "molejo": 1,
        "profile": {"type": "circle", "radius": wire},
        "path": [
            {"type": "line", "to": [0.0, 0.0, rise]},
            {
                "type": "arc",
                "center": [radius, 0.0, rise],
                "axis": [0.0, 1.0, 0.0],
                "angle": QUARTER,
            },
            {"type": "line", "to": [reach, 0.0, rise + radius]},
        ],
        "loop": False,
        "tessellation": {"path": path, "profile": profile},
    }


def elbow(angle=QUARTER, wire=1.5, radius=6.0, path=24, profile=48):
    """The bend's arc on its own, so the arc answers for its own geometry."""
    return {
        "molejo": 1,
        "profile": {"type": "circle", "radius": wire},
        "path": [
            {
                "type": "arc",
                "center": [radius, 0.0, 0.0],
                "axis": [0.0, 1.0, 0.0],
                "angle": angle,
            }
        ],
        "loop": False,
        "tessellation": {"path": path, "profile": profile},
    }


def spring(wire=1.0, radius=6.0, turns=2.5, height=30.0, path=48, profile=24):
    """A coil spring: the helix a valve spring is."""
    return {
        "molejo": 1,
        "profile": {"type": "circle", "radius": wire},
        "path": [{"type": "helix", "radius": radius, "turns": turns, "height": height}],
        "loop": False,
        "tessellation": {"path": path, "profile": profile},
    }


# --- independent closed forms ----------------------------------------------


def polygon_area(profile, wire):
    """The area of the regular M-gon the profile samples to."""
    return 0.5 * profile * wire * wire * math.sin(2.0 * math.pi / profile)


def sampled_volume(profile, wire, chords, tangents):
    """The volume the sampling describes, in closed form.

    Between two rings the mesh is the M-gon carried along the chord and
    tilted by half the tangent's turn at each end. Its footprint on the
    plane across the chord is the M-gon squashed by that half-turn's
    cosine, and the wall generators are parallel to the chord, so the
    piece encloses exactly `A * chord * cos(half turn)` -- the mitre neither
    adds nor removes volume, the squash is the whole of it.
    """
    turn = np.arccos(
        np.clip(np.einsum("ij,ij->i", tangents[:-1], tangents[1:]), -1.0, 1.0)
    )
    return float(np.sum(polygon_area(profile, wire) * chords * np.cos(turn / 2.0)))


def tube_volume(wire, length):
    """A tube of radius `wire` about a curve of length `length`.

    Exactly pi*a^2*L for any embedded curve in space -- the curvature
    corrections of the tube formula vanish in three dimensions -- so this
    is an analytic expectation for an arc and a helix alike, not an
    approximation of one.
    """
    return math.pi * wire * wire * length


def chord_shortfall(turn):
    """How far below the arc a chord subtending `turn` radians falls."""
    return 1.0 - math.sin(turn / 2.0) / (turn / 2.0)


def bend_rings(reach=20.0, radius=6.0, rise=10.0, path=4):
    """The quarter bend's rings, predicted in closed form.

    The line up +Z leaves the start frame alone (its tangent is the start
    frame's), the arc turns about +Y so the frame turns about +Y with it,
    and the second line inherits the arc's end frame unchanged because it
    leaves along the arc's end tangent. Rings 0..path-1 belong to the
    first line, path..2*path-1 to the arc, and 2*path..3*path to the
    second line: a joint's ring is sampled once, by the primitive that
    leaves it.
    """
    centres, axes = [], []
    for i in range(path):
        centres.append((0.0, 0.0, rise * i / path))
        axes.append(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
    for i in range(path):
        phi = QUARTER * i / path
        centres.append(
            (radius - radius * math.cos(phi), 0.0, rise + radius * math.sin(phi))
        )
        axes.append(((math.cos(phi), 0.0, -math.sin(phi)), (0.0, 1.0, 0.0)))
    for i in range(path + 1):
        centres.append(
            (radius + (reach - radius) * i / path, 0.0, rise + radius)
        )
        axes.append(((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)))
    return np.array(centres), np.array(axes)


def profile_offsets(profile, wire):
    """The circle profile's (u, v) coordinates, as design.md pins them."""
    angles = 2.0 * math.pi * np.arange(profile) / profile
    return wire * np.column_stack([np.cos(angles), np.sin(angles)])


def helix_centres(radius=6.0, turns=2.5, height=30.0, path=48):
    """The helix's ring centres: it starts at the origin and winds about
    +Z through the point (-radius, 0, 0)."""
    steps = np.arange(path + 1) / path
    phi = 2.0 * math.pi * turns * steps
    return np.column_stack(
        [-radius + radius * np.cos(phi), radius * np.sin(phi), height * steps]
    )


def helix_tangents(radius=6.0, turns=2.5, height=30.0, path=48):
    steps = np.arange(path + 1) / path
    phi = 2.0 * math.pi * turns * steps
    speed = 2.0 * math.pi * turns * radius
    tangents = np.column_stack(
        [-speed * np.sin(phi), speed * np.cos(phi), np.full(path + 1, height)]
    )
    return tangents / np.linalg.norm(tangents, axis=1)[:, None]


def helix_length(radius=6.0, turns=2.5, height=30.0):
    return math.hypot(2.0 * math.pi * turns * radius, height)


def helix_chord(radius=6.0, turns=2.5, height=30.0, path=48):
    """One sampling step of a helix, chord rather than arc.

    A screw motion carries each step onto the next, so every step is the
    same chord: the circle's `2*R*sin(half turn)` across, the pitch's
    share along.
    """
    return math.hypot(
        2.0 * radius * math.sin(math.pi * turns / path), height / path
    )


def rings_of(mesh, profile):
    """The wall vertices as (rings, profile, 3), the two cap centres apart."""
    walls = mesh.vertices[:-2]
    return walls.reshape(-1, profile, 3)


# --- how tessellation.path is spent ----------------------------------------


def test_a_chain_spends_the_declared_segments_on_every_primitive():
    # Three primitives at 4 segments each: 12 segments, 13 rings.
    mesh = molejo.evaluate(bend(path=4, profile=8))
    assert mesh.vertices.shape == (13 * 8 + 2, 3)
    assert mesh.faces.shape == (2 * 12 * 8 + 2 * 8, 3)


def test_one_primitive_is_still_n_plus_one_rings():
    # The count the cylinder fixture pinned must read the same way.
    mesh = molejo.evaluate(elbow(path=6, profile=8))
    assert mesh.vertices.shape == (7 * 8 + 2, 3)


def test_the_ring_count_does_not_follow_a_parameter():
    document = bend(reach={"param": "reach"})
    near = molejo.evaluate(document, {"reach": 20.0})
    far = molejo.evaluate(document, {"reach": 80.0})
    assert near.vertices.shape == far.vertices.shape
    assert np.array_equal(near.faces, far.faces)
    assert not np.array_equal(near.vertices, far.vertices)


def test_the_ring_count_does_not_follow_the_arc_length_either():
    # A quarter turn and a full turn are wildly different lengths and get
    # exactly the same number of rings: distribution is a function of the
    # document alone.
    short = molejo.evaluate(elbow(angle=QUARTER, path=8, profile=8))
    long = molejo.evaluate(elbow(angle=2.0 * math.pi * 0.9, path=8, profile=8))
    assert short.vertices.shape == long.vertices.shape
    assert np.array_equal(short.faces, long.faces)


# --- the quarter bend, vertex by vertex ------------------------------------


def test_every_ring_of_the_bend_sits_where_the_closed_form_says():
    path, profile, reach = 4, 8, 20.0
    mesh = molejo.evaluate(bend(reach=reach, path=path, profile=profile))
    centres, _ = bend_rings(reach=reach, path=path)
    assert rings_of(mesh, profile).mean(axis=1) == pytest.approx(centres, abs=1e-12)


def test_every_wall_vertex_of_the_bend_is_the_closed_form_vertex():
    path, profile, reach, wire = 4, 8, 20.0, 1.5
    mesh = molejo.evaluate(bend(reach=reach, wire=wire, path=path, profile=profile))
    centres, axes = bend_rings(reach=reach, path=path)
    offsets = profile_offsets(profile, wire)
    expected = (
        centres[:, None, :]
        + offsets[None, :, 0, None] * axes[:, None, 0, :]
        + offsets[None, :, 1, None] * axes[:, None, 1, :]
    )
    assert rings_of(mesh, profile) == pytest.approx(expected, abs=1e-12)


def test_the_joint_rings_are_shared_and_not_duplicated():
    path, profile = 4, 8
    mesh = molejo.evaluate(bend(path=path, profile=profile))
    centres = rings_of(mesh, profile).mean(axis=1)
    steps = np.linalg.norm(np.diff(centres, axis=0), axis=1)
    assert (steps > 1e-9).all(), "a duplicated joint ring would leave a zero step"
    assert centres[path] == pytest.approx((0.0, 0.0, 10.0), abs=1e-12)
    assert centres[2 * path] == pytest.approx((6.0, 0.0, 16.0), abs=1e-12)


def test_a_tangent_continuous_joint_shows_no_twist_jump():
    # The rings on either side of a joint are drawn by different
    # primitives, so a joint is where a seam would show. Follow vertex 0 --
    # the one in the plane the arc turns in -- from ring to ring: the roll
    # is zero along both lines, exactly one arc step through the bend, and
    # neither joint adds a step of its own or skips one.
    path, profile, wire = 4, 8, 1.5
    mesh = molejo.evaluate(bend(wire=wire, path=path, profile=profile))
    rings = rings_of(mesh, profile)
    spokes = (rings - rings.mean(axis=1)[:, None, :])[:, 0, :] / wire
    rolled = np.arccos(np.clip(np.einsum("ij,ij->i", spokes[:-1], spokes[1:]), -1.0, 1.0))

    step = QUARTER / path
    expected = np.concatenate(
        [np.zeros(path), np.full(path, step), np.zeros(path)]
    )
    assert rolled == pytest.approx(expected, abs=1e-12)


def test_the_bend_is_watertight_and_winds_outward():
    mesh = molejo.evaluate(bend(path=6, profile=16))
    assert watertight_failures(mesh.faces) == []
    assert signed_volume(mesh) > 0.0


# --- the arc answers for its own geometry ----------------------------------


@pytest.mark.parametrize("angle", [0.25, QUARTER, math.pi, 5.0], ids=str)
def test_arc_rings_ride_the_circle_at_a_constant_radius(angle):
    radius, path, profile = 6.0, 24, 48
    mesh = molejo.evaluate(elbow(angle=angle, radius=radius, path=path, profile=profile))
    centres = rings_of(mesh, profile).mean(axis=1)

    # Distance to the axis line (through the centre, along +Y) is the arc's
    # radius at every ring, and the arc stays in the plane y = 0.
    offset = centres - np.array([radius, 0.0, 0.0])
    assert offset[:, 1] == pytest.approx(np.zeros(path + 1), abs=1e-12)
    assert np.linalg.norm(offset, axis=1) == pytest.approx(
        np.full(path + 1, radius), abs=1e-12
    )
    # Uniform in angle: every step subtends the same angle.
    turns = np.unwrap(np.arctan2(offset[:, 2], -offset[:, 0]))
    assert np.diff(turns) == pytest.approx(np.full(path, angle / path), abs=1e-12)


def test_a_negative_angle_turns_the_other_way():
    radius, path, profile = 6.0, 8, 8
    forward = molejo.evaluate(elbow(angle=QUARTER, radius=radius, path=path, profile=profile))
    backward = molejo.evaluate(
        elbow(angle=-QUARTER, radius=radius, path=path, profile=profile)
    )
    forward_end = rings_of(forward, profile).mean(axis=1)[-1]
    backward_end = rings_of(backward, profile).mean(axis=1)[-1]
    assert forward_end == pytest.approx((radius, 0.0, radius), abs=1e-12)
    assert backward_end == pytest.approx((radius, 0.0, -radius), abs=1e-12)
    assert signed_volume(backward) > 0.0, "a reversed arc must not turn inside out"


def test_every_arc_ring_is_a_circle_perpendicular_to_the_tangent():
    radius, wire, path, profile, angle = 6.0, 1.5, 24, 48, QUARTER
    mesh = molejo.evaluate(
        elbow(angle=angle, wire=wire, radius=radius, path=path, profile=profile)
    )
    rings = rings_of(mesh, profile)
    centres = rings.mean(axis=1)
    spokes = rings - centres[:, None, :]

    assert np.linalg.norm(spokes, axis=2) == pytest.approx(
        np.full((path + 1, profile), wire), abs=1e-12
    ), "the profile stayed a circle of the wire's radius"

    phi = angle * np.arange(path + 1) / path
    tangents = np.column_stack([np.sin(phi), np.zeros(path + 1), np.cos(phi)])
    assert np.einsum("ijk,ik->ij", spokes, tangents) == pytest.approx(
        np.zeros((path + 1, profile)), abs=1e-12
    ), "every ring lies in the plane perpendicular to the analytic tangent"


def test_the_arc_encloses_the_volume_the_sampling_describes_exactly():
    radius, wire, path, profile, angle = 6.0, 1.5, 24, 48, QUARTER
    mesh = molejo.evaluate(
        elbow(angle=angle, wire=wire, radius=radius, path=path, profile=profile)
    )
    # For a planar arc the two mitres are exactly the arc's own step, so
    # the closed form collapses to N * A * R * sin(step) and holds to the
    # last bit -- the arc's answer to the cylinder's prism volume.
    step = angle / path
    exact = path * polygon_area(profile, wire) * radius * math.sin(step)
    assert signed_volume(mesh) == pytest.approx(exact, rel=1e-12)

    analytic = tube_volume(wire, radius * angle)
    assert signed_volume(mesh) < analytic, "an inscribed sampling cannot exceed the tube"
    assert signed_volume(mesh) == pytest.approx(
        analytic * (1.0 - chord_deficit(profile)) * (1.0 - chord_shortfall(step)),
        rel=1e-3,
    )


def test_sliding_the_declared_centre_along_the_axis_changes_nothing():
    # Only the component of (start - centre) across the axis turns, so the
    # `center` slot names the axis line, not a point the arc cares about.
    here = molejo.evaluate(elbow(path=8, profile=12))
    document = elbow(path=8, profile=12)
    document["path"][0]["center"] = [6.0, 25.0, 0.0]
    assert molejo.evaluate(document).vertices == pytest.approx(here.vertices, abs=1e-12)


def test_the_axis_is_normalized_before_it_is_used():
    document = elbow(path=8, profile=12)
    document["path"][0]["axis"] = [0.0, 37.5, 0.0]
    assert molejo.evaluate(document).vertices == pytest.approx(
        molejo.evaluate(elbow(path=8, profile=12)).vertices, abs=1e-12
    )


# --- the helix -------------------------------------------------------------


def test_helix_rings_ride_the_analytic_curve():
    radius, turns, height, path, profile = 6.0, 2.5, 30.0, 48, 24
    mesh = molejo.evaluate(
        spring(radius=radius, turns=turns, height=height, path=path, profile=profile)
    )
    centres = rings_of(mesh, profile).mean(axis=1)
    assert centres == pytest.approx(
        helix_centres(radius, turns, height, path), abs=1e-12
    )
    assert centres[0] == pytest.approx((0.0, 0.0, 0.0), abs=1e-12), "it starts where it is"


def test_the_helix_winds_right_handed_about_the_incoming_tangent():
    # x turns toward y about +Z: the first step must leave the start point
    # with a positive y and a positive z.
    mesh = molejo.evaluate(spring(path=48, profile=8))
    centres = rings_of(mesh, 8).mean(axis=1)
    assert centres[1][1] > 0.0 and centres[1][2] > 0.0


def test_every_helix_ring_is_a_circle_perpendicular_to_the_tangent():
    radius, wire, turns, height, path, profile = 6.0, 1.0, 2.5, 30.0, 48, 24
    mesh = molejo.evaluate(
        spring(
            wire=wire,
            radius=radius,
            turns=turns,
            height=height,
            path=path,
            profile=profile,
        )
    )
    rings = rings_of(mesh, profile)
    spokes = rings - rings.mean(axis=1)[:, None, :]

    assert np.linalg.norm(spokes, axis=2) == pytest.approx(
        np.full((path + 1, profile), wire), abs=1e-12
    ), "the wire's cross-section stayed a circle"

    tangents = helix_tangents(radius, turns, height, path)
    assert np.einsum("ijk,ik->ij", spokes, tangents) == pytest.approx(
        np.zeros((path + 1, profile)), abs=1e-12
    ), "no axial shear: every ring is perpendicular to the local tangent"


def test_the_first_helix_ring_is_the_start_frame_carried_onto_the_pitch():
    radius, wire, turns, height, path, profile = 6.0, 1.0, 2.5, 30.0, 48, 24
    mesh = molejo.evaluate(
        spring(
            wire=wire,
            radius=radius,
            turns=turns,
            height=height,
            path=path,
            profile=profile,
        )
    )
    frame = transport(START_FRAME, helix_tangents(radius, turns, height, path)[0])
    offsets = profile_offsets(profile, wire)
    expected = offsets[:, 0, None] * frame.x + offsets[:, 1, None] * frame.y
    assert rings_of(mesh, profile)[0] == pytest.approx(expected, abs=1e-12)


def test_the_coil_count_does_not_move_when_the_pitch_does():
    turns, path, profile = 2.5, 48, 24
    document = spring(turns=turns, height={"param": "height"}, path=path, profile=profile)
    free = molejo.evaluate(document, {"height": 30.0})
    compressed = molejo.evaluate(document, {"height": 12.0})

    assert free.vertices.shape == compressed.vertices.shape
    assert np.array_equal(free.faces, compressed.faces)
    assert not np.array_equal(free.vertices, compressed.vertices)

    for mesh in (free, compressed):
        centres = rings_of(mesh, profile).mean(axis=1)
        # Total angle swept about the helix axis, which runs through
        # (-radius, 0) in the start frame's x/y.
        angles = np.unwrap(np.arctan2(centres[:, 1], centres[:, 0] + 6.0))
        assert float(angles[-1] - angles[0]) == pytest.approx(
            2.0 * math.pi * turns, abs=1e-9
        )


def test_a_compressed_spring_keeps_a_round_wire():
    # The point of the fixture: compression must not shear the wire into
    # an ellipse, which is what a frame that ignored the pitch would do.
    document = spring(wire=1.0, height={"param": "height"}, path=48, profile=24)
    for height in (30.0, 12.0, 0.0):
        mesh = molejo.evaluate(document, {"height": height})
        rings = rings_of(mesh, 24)
        spokes = rings - rings.mean(axis=1)[:, None, :]
        assert np.linalg.norm(spokes, axis=2) == pytest.approx(
            np.full((49, 24), 1.0), abs=1e-12
        ), f"height {height}"


def test_the_helix_rings_are_uniform_in_arc_length():
    radius, turns, height, path, profile = 6.0, 2.5, 30.0, 48, 24
    mesh = molejo.evaluate(
        spring(radius=radius, turns=turns, height=height, path=path, profile=profile)
    )
    centres = rings_of(mesh, profile).mean(axis=1)
    steps = np.linalg.norm(np.diff(centres, axis=0), axis=1)
    chord = helix_chord(radius, turns, height, path)
    assert steps == pytest.approx(np.full(path, chord), rel=1e-12)
    assert steps.sum() < helix_length(radius, turns, height), (
        "a chord polyline cannot exceed its curve"
    )


def test_the_helix_encloses_the_tube_volume_the_sampling_describes():
    radius, wire, turns, height, path, profile = 6.0, 1.0, 2.5, 30.0, 48, 24
    mesh = molejo.evaluate(
        spring(
            wire=wire,
            radius=radius,
            turns=turns,
            height=height,
            path=path,
            profile=profile,
        )
    )
    analytic = tube_volume(wire, helix_length(radius, turns, height))
    sampled = sampled_volume(
        profile,
        wire,
        np.full(path, helix_chord(radius, turns, height, path)),
        helix_tangents(radius, turns, height, path),
    )
    assert watertight_failures(mesh.faces) == []
    # Not exact as the arc's is: a helix's mitre planes are not quite
    # square to its chords, and the residual falls away as the cube of the
    # sampling (1.4e-5 here, 3.4e-8 at eight times the rings).
    assert signed_volume(mesh) == pytest.approx(sampled, rel=1e-4)
    assert signed_volume(mesh) < analytic, "an inscribed sampling cannot exceed the tube"


def test_a_flat_helix_is_a_circle_and_a_negative_height_advances_backwards():
    flat = molejo.evaluate(spring(height=0.0, turns=1.0, path=32, profile=8))
    centres = rings_of(flat, 8).mean(axis=1)
    assert centres[:, 2] == pytest.approx(np.zeros(33), abs=1e-12)
    assert centres[-1] == pytest.approx(centres[0], abs=1e-12), "one turn comes back"

    down = molejo.evaluate(spring(height=-30.0, path=48, profile=8))
    assert rings_of(down, 8).mean(axis=1)[-1][2] == pytest.approx(-30.0, abs=1e-12)


def test_a_left_handed_spring_is_the_mirror_of_a_right_handed_one():
    right = molejo.evaluate(spring(turns=2.5, path=48, profile=8))
    left = molejo.evaluate(spring(turns=-2.5, path=48, profile=8))
    mirrored = rings_of(left, 8).mean(axis=1) * np.array([1.0, -1.0, 1.0])
    assert mirrored == pytest.approx(rings_of(right, 8).mean(axis=1), abs=1e-12)


# --- chains of curves ------------------------------------------------------


def test_a_helix_may_follow_a_line_and_start_where_it_ended():
    document = spring(path=8, profile=8)
    document["path"] = [{"type": "line", "to": [0.0, 0.0, 4.0]}] + document["path"]
    mesh = molejo.evaluate(document)
    centres = rings_of(mesh, 8).mean(axis=1)
    assert len(centres) == 17
    assert centres[8] == pytest.approx((0.0, 0.0, 4.0), abs=1e-12)
    # The helix winds about the line's tangent from the line's end: its
    # axis runs through (-6, 0, 4), and 2.5 turns end on the far side.
    assert centres[-1] == pytest.approx((-12.0, 0.0, 34.0), abs=1e-9)
    assert watertight_failures(mesh.faces) == []


def test_an_authored_chain_evaluates_like_its_document():
    shape = Shape(
        profile=Circle(radius=1.5),
        path=[
            Line(to=(0.0, 0.0, 10.0)),
            Arc(center=(6.0, 0.0, 10.0), axis=(0.0, 1.0, 0.0), angle=QUARTER),
            Line(to=(P.reach, 0.0, 16.0)),
        ],
        path_samples=4,
        profile_samples=8,
    )
    authored = shape.evaluate(reach=20.0)
    document = molejo.evaluate(bend(reach={"param": "reach"}), {"reach": 20.0})
    assert authored.vertices.tobytes() == document.vertices.tobytes()
    assert authored.faces.tobytes() == document.faces.tobytes()


def test_a_chained_evaluation_is_bitwise_repeatable():
    document = bend(reach={"param": "reach"})
    first = molejo.evaluate(document, {"reach": 17.5})
    second = molejo.evaluate(document, {"reach": 17.5})
    assert first.vertices.tobytes() == second.vertices.tobytes()


# --- degeneracies are refused, naming the slot -----------------------------


def test_an_arc_with_a_zero_axis_is_refused():
    document = elbow()
    document["path"][0]["axis"] = [0.0, 0.0, 0.0]
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document)
    assert "path[0].axis" in str(caught.value)


def test_an_arc_whose_start_lies_on_its_axis_is_refused():
    document = elbow()
    document["path"][0]["center"] = [0.0, 0.0, 0.0]
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document)
    assert "path[0].center" in str(caught.value)


def test_an_arc_that_turns_nowhere_is_refused():
    document = elbow(angle=0.0)
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document)
    assert "path[0].angle" in str(caught.value)


def test_a_helix_with_a_non_positive_radius_is_refused():
    document = spring(radius={"param": "coil"})
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {"coil": 0.0})
    assert "path[0].radius" in str(caught.value)


def test_a_helix_that_goes_nowhere_is_refused():
    document = spring(turns=0.0, height=0.0)
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document)
    assert "path[0]" in str(caught.value)


def test_a_degenerate_primitive_names_its_own_position_in_the_chain():
    document = bend()
    document["path"][1]["angle"] = 0.0
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document)
    assert "path[1].angle" in str(caught.value)


def test_a_dangling_parameter_in_a_later_primitive_names_that_slot():
    document = bend(reach={"param": "reach"})
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    assert "path[2].to[0]" in str(caught.value)
    assert "reach" in str(caught.value)


# --- what this batch still does not evaluate -------------------------------


def test_an_unimplemented_primitive_in_a_chain_names_its_position():
    primitive = {"type": "spline", "points": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]}
    document = bend()
    document["path"][2] = primitive
    with pytest.raises(NotImplementedError) as caught:
        molejo.evaluate(document)
    message = str(caught.value)
    assert "path[2]" in message
    assert primitive["type"] in message
    assert "not implemented" in message


def test_a_chained_loop_is_still_not_evaluated():
    document = bend()
    document["loop"] = True
    with pytest.raises(NotImplementedError, match="loop"):
        molejo.evaluate(document)
