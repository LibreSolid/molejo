# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The first vertical slice: a circle profile swept along one line.

The cylinder is the smallest shape that exercises everything a sweep
does -- profile sampling, frame transport, ring assembly, capping, and
parameter resolution -- and it is the one shape whose mesh can be
checked against closed-form arithmetic rather than against itself.

The conventions asserted here (ring-major wall vertices, the two cap
centres last, walls-then-caps face ordering, outward winding) are the
ones design.md pins under "Sweep evaluation conventions": the JS twin,
the parity fixtures, and every later primitive are built on them, so
they are asserted directly and not merely implied by a volume.
"""

import math
from collections import Counter

import numpy as np
import pytest

import molejo
from molejo import Circle, Line, P, Shape
from molejo.evaluator import EvaluationError

# --- the shape under test --------------------------------------------------


def cylinder(radius=5.0, length=12.0, path=4, profile=64):
    """A circle profile swept along one line up the +Z axis."""
    return {
        "molejo": 1,
        "profile": {"type": "circle", "radius": radius},
        "path": [{"type": "line", "to": [0.0, 0.0, length]}],
        "loop": False,
        "tessellation": {"path": path, "profile": profile},
    }


# --- independent mesh arithmetic -------------------------------------------
#
# Deliberately not the evaluator's own helpers: a mesh that is watertight
# because both sides of the assertion share a bug proves nothing.


def signed_volume(mesh):
    """The divergence-theorem volume of a closed oriented triangle mesh."""
    triangles = mesh.vertices[mesh.faces]
    return float(
        np.einsum(
            "ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])
        ).sum()
        / 6.0
    )


def directed_edges(faces):
    counts = Counter()
    for a, b, c in faces:
        counts[(a, b)] += 1
        counts[(b, c)] += 1
        counts[(c, a)] += 1
    return counts


def watertight_failures(faces):
    """Every way a triangle set fails to be a closed oriented surface."""
    counts = directed_edges(faces)
    failures = []
    for edge, count in counts.items():
        if count != 1:
            failures.append(f"directed edge {edge} used {count} times")
        opposite = counts[(edge[1], edge[0])]
        if opposite != 1:
            failures.append(f"edge {edge} has {opposite} opposite uses")
    return failures


def prism_volume(radius, length, profile):
    """The exact volume of the M-gon prism the tessellation describes."""
    return 0.5 * profile * radius * radius * math.sin(2 * math.pi / profile) * length


def chord_deficit(profile):
    """How far below pi*r^2*h an M-gon prism necessarily falls."""
    return 1.0 - (profile / (2 * math.pi)) * math.sin(2 * math.pi / profile)


# --- counts, ordering, and winding -----------------------------------------


def test_a_cylinder_has_the_counts_the_tessellation_declares():
    mesh = molejo.evaluate(cylinder(path=4, profile=64))
    # 5 rings of 64 wall vertices, then the two cap centres.
    assert mesh.vertices.shape == (5 * 64 + 2, 3)
    # Two triangles per wall quad, plus a fan triangle per cap edge.
    assert mesh.faces.shape == (2 * 4 * 64 + 2 * 64, 3)


def test_the_counts_do_not_follow_the_parameter():
    short = molejo.evaluate(cylinder(length={"param": "length"}), {"length": 3.0})
    tall = molejo.evaluate(cylinder(length={"param": "length"}), {"length": 300.0})
    assert short.vertices.shape == tall.vertices.shape
    assert np.array_equal(short.faces, tall.faces)


def test_wall_vertices_are_ring_major_at_the_declared_angles():
    radius, length, path, profile = 5.0, 12.0, 4, 12
    mesh = molejo.evaluate(cylinder(radius, length, path, profile))
    for ring in range(path + 1):
        for j in range(profile):
            angle = 2 * math.pi * j / profile
            expected = (
                radius * math.cos(angle),
                radius * math.sin(angle),
                length * ring / path,
            )
            assert mesh.vertices[ring * profile + j] == pytest.approx(expected, abs=1e-12)


def test_the_last_two_vertices_are_the_cap_centres():
    radius, length, path, profile = 5.0, 12.0, 4, 12
    mesh = molejo.evaluate(cylinder(radius, length, path, profile))
    rings = path + 1
    assert mesh.vertices[rings * profile] == pytest.approx((0.0, 0.0, 0.0), abs=1e-12)
    assert mesh.vertices[rings * profile + 1] == pytest.approx(
        (0.0, 0.0, length), abs=1e-12
    )


def test_faces_run_walls_then_start_cap_then_end_cap():
    path, profile = 4, 12
    mesh = molejo.evaluate(cylinder(path=path, profile=profile))
    walls = 2 * path * profile
    start_centre = (path + 1) * profile
    end_centre = start_centre + 1

    # The first two faces are the two triangles of wall quad (ring 0, j 0).
    assert mesh.faces[0].tolist() == [0, 1, profile + 1]
    assert mesh.faces[1].tolist() == [0, profile + 1, profile]

    start_fan = mesh.faces[walls : walls + profile]
    end_fan = mesh.faces[walls + profile :]
    assert (start_fan[:, 0] == start_centre).all()
    assert (end_fan[:, 0] == end_centre).all()
    # The start fan winds backwards around ring 0 so it faces -tangent.
    assert start_fan[0].tolist() == [start_centre, 1, 0]
    last_ring = path * profile
    assert end_fan[0].tolist() == [end_centre, last_ring, last_ring + 1]


def test_every_triangle_faces_outward():
    radius, length, path, profile = 5.0, 12.0, 4, 24
    mesh = molejo.evaluate(cylinder(radius, length, path, profile))
    triangles = mesh.vertices[mesh.faces]
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    axis_centre = np.array([0.0, 0.0, length / 2.0])
    outward = triangles.mean(axis=1) - axis_centre
    assert (np.einsum("ij,ij->i", normals, outward) > 0.0).all()


def test_a_cylinder_is_watertight():
    mesh = molejo.evaluate(cylinder(path=4, profile=24))
    assert watertight_failures(mesh.faces) == []


def test_the_volume_is_the_declared_prisms_volume_exactly():
    radius, length, path, profile = 5.0, 12.0, 4, 64
    mesh = molejo.evaluate(cylinder(radius, length, path, profile))
    expected = prism_volume(radius, length, profile)
    assert signed_volume(mesh) == pytest.approx(expected, rel=1e-12)


def test_the_volume_approaches_the_analytic_cylinder_within_the_chord_error():
    radius, length, profile = 5.0, 12.0, 64
    mesh = molejo.evaluate(cylinder(radius, length, 4, profile))
    analytic = math.pi * radius * radius * length
    deficit = chord_deficit(profile)
    assert deficit == pytest.approx(0.0016, abs=1e-4), "a 64-gon falls 0.16% short"
    assert signed_volume(mesh) == pytest.approx(analytic, rel=2 * deficit)
    assert signed_volume(mesh) < analytic, "an inscribed prism cannot exceed the cylinder"


def test_the_arrays_are_float64_vertices_and_integer_faces():
    mesh = molejo.evaluate(cylinder())
    assert mesh.vertices.dtype == np.float64
    assert np.issubdtype(mesh.faces.dtype, np.integer)


# --- frame transport --------------------------------------------------------
#
# A line has one tangent, so transport along it is the identity; what has to
# be right is the single turn from the start frame (+Z) onto that tangent.
# The arc and helix batches transport per ring on top of this, so the helper
# is asserted directly and not only through the cylinder it produces.


def slanted(to, radius=5.0, path=4, profile=24):
    return {
        "molejo": 1,
        "profile": {"type": "circle", "radius": radius},
        "path": [{"type": "line", "to": list(to)}],
        "loop": False,
        "tessellation": {"path": path, "profile": profile},
    }


@pytest.mark.parametrize(
    "to",
    [(10.0, 0.0, 0.0), (0.0, 7.0, 0.0), (0.0, 0.0, -12.0), (3.0, 4.0, 12.0)],
    ids=["+x", "+y", "-z reversed", "oblique"],
)
def test_a_line_in_any_direction_sweeps_a_round_tube(to):
    radius, profile = 5.0, 24
    mesh = molejo.evaluate(slanted(to, radius=radius, profile=profile))
    axis = np.array(to) / np.linalg.norm(to)

    walls = mesh.vertices[:-2]
    along = walls @ axis
    radial = np.linalg.norm(walls - along[:, None] * axis, axis=1)
    assert radial == pytest.approx(radius, abs=1e-12), "the profile stayed circular"

    length = float(np.linalg.norm(to))
    assert signed_volume(mesh) == pytest.approx(
        prism_volume(radius, length, profile), rel=1e-12
    )
    assert watertight_failures(mesh.faces) == []


def test_a_reversed_path_still_winds_outward():
    # The tangent is antiparallel to the start frame's: the one direction
    # with no minimal rotation, so the axis is chosen deterministically.
    mesh = molejo.evaluate(slanted((0.0, 0.0, -12.0)))
    assert signed_volume(mesh) > 0.0, "a reversed sweep must not turn inside out"
    assert molejo.evaluate(slanted((0.0, 0.0, -12.0))).vertices.tobytes() == (
        mesh.vertices.tobytes()
    ), "the antiparallel axis choice must be deterministic"


def test_transport_onto_the_same_tangent_changes_nothing():
    from molejo.evaluator import START_FRAME, minimal_rotation, transport

    assert (minimal_rotation((0.0, 0.0, 1.0), (0.0, 0.0, 1.0)) == np.identity(3)).all()
    carried = transport(START_FRAME, (0.0, 0.0, 1.0))
    assert (carried.x == START_FRAME.x).all()
    assert (carried.y == START_FRAME.y).all()


@pytest.mark.parametrize(
    "tangent",
    [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (0.6, 0.0, 0.8)],
    ids=["+x", "+y", "-z", "oblique"],
)
def test_transport_keeps_the_frame_orthonormal_and_right_handed(tangent):
    from molejo.evaluator import START_FRAME, transport

    carried = transport(START_FRAME, tangent)
    assert np.linalg.norm(carried.x) == pytest.approx(1.0, abs=1e-12)
    assert np.linalg.norm(carried.y) == pytest.approx(1.0, abs=1e-12)
    assert float(carried.x @ carried.y) == pytest.approx(0.0, abs=1e-12)
    assert float(carried.x @ carried.tangent) == pytest.approx(0.0, abs=1e-12)
    assert np.cross(carried.x, carried.y) == pytest.approx(tangent, abs=1e-12)


def test_transport_turns_by_the_angle_between_the_tangents():
    from molejo.evaluator import START_FRAME, transport

    carried = transport(START_FRAME, (1.0, 0.0, 0.0))
    # +Z onto +X is a quarter turn about -Y; the profile's own x-axis is
    # carried onto -Z and its y-axis is left alone.
    assert carried.x == pytest.approx((0.0, 0.0, -1.0), abs=1e-12)
    assert carried.y == pytest.approx((0.0, 1.0, 0.0), abs=1e-12)


# --- determinism ------------------------------------------------------------


def test_repeated_evaluation_is_bitwise_identical():
    document = cylinder(length={"param": "length"})
    first = molejo.evaluate(document, {"length": 17.5})
    second = molejo.evaluate(document, {"length": 17.5})
    assert first.vertices.tobytes() == second.vertices.tobytes()
    assert first.faces.tobytes() == second.faces.tobytes()


def test_two_bindings_give_two_meshes():
    document = cylinder(length={"param": "length"})
    short = molejo.evaluate(document, {"length": 5.0})
    tall = molejo.evaluate(document, {"length": 50.0})
    assert not np.array_equal(short.vertices, tall.vertices)
    assert signed_volume(tall) == pytest.approx(10.0 * signed_volume(short), rel=1e-12)


def test_a_parameter_bound_to_the_literal_value_reproduces_the_literal_shape():
    literal = molejo.evaluate(cylinder(length=12.0))
    bound = molejo.evaluate(cylinder(length={"param": "length"}), {"length": 12.0})
    assert bound.vertices.tobytes() == literal.vertices.tobytes()


def test_a_parameter_may_drive_any_slot():
    document = cylinder(radius={"param": "wire"}, length={"param": "length"})
    mesh = molejo.evaluate(document, {"wire": 2.0, "length": 30.0})
    assert signed_volume(mesh) == pytest.approx(
        prism_volume(2.0, 30.0, 64), rel=1e-12
    )


def test_values_the_spec_does_not_reference_are_ignored():
    document = cylinder(length={"param": "length"})
    plain = molejo.evaluate(document, {"length": 9.0})
    noisy = molejo.evaluate(document, {"length": 9.0, "motor_angle": 1.7, "lift": 0.0})
    assert plain.vertices.tobytes() == noisy.vertices.tobytes()


# --- authored shapes evaluate ----------------------------------------------


def test_an_authored_shape_evaluates_like_its_document():
    shape = Shape(
        profile=Circle(radius=5.0),
        path=[Line(to=(0.0, 0.0, P.length))],
        path_samples=4,
        profile_samples=64,
    )
    authored = shape.evaluate(length=12.0)
    document = molejo.evaluate(shape.to_dict(), {"length": 12.0})
    assert authored.vertices.tobytes() == document.vertices.tobytes()
    assert authored.faces.tobytes() == document.faces.tobytes()


# --- loud failure, no partial output ---------------------------------------


def test_a_dangling_parameter_raises_naming_it_and_the_slot():
    document = cylinder(length={"param": "length"})
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {})
    message = str(caught.value)
    assert "length" in message
    assert "path[0].to[2]" in message


def test_a_dangling_parameter_names_only_the_first_offender():
    document = cylinder(radius={"param": "wire"}, length={"param": "length"})
    with pytest.raises(EvaluationError, match="wire"):
        molejo.evaluate(document, {"length": 12.0})


def test_a_non_numeric_value_raises_naming_the_parameter():
    document = cylinder(length={"param": "lift"})
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document, {"lift": "high"})
    message = str(caught.value)
    assert "lift" in message
    assert "a string" in message


def test_a_boolean_is_not_a_number():
    document = cylinder(length={"param": "lift"})
    with pytest.raises(EvaluationError, match="a boolean"):
        molejo.evaluate(document, {"lift": True})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_a_non_finite_value_raises(value):
    document = cylinder(length={"param": "lift"})
    with pytest.raises(EvaluationError, match="finite"):
        molejo.evaluate(document, {"lift": value})


def test_an_invalid_document_is_rejected_before_any_geometry():
    with pytest.raises(molejo.SpecError, match="squiggle"):
        molejo.evaluate(
            {
                "molejo": 1,
                "profile": {"type": "circle", "radius": 1.0},
                "path": [{"type": "squiggle"}],
                "tessellation": {"path": 4, "profile": 8},
            }
        )


def test_a_line_with_no_direction_is_refused():
    document = cylinder(length=0.0)
    with pytest.raises(EvaluationError) as caught:
        molejo.evaluate(document)
    assert "path[0].to" in str(caught.value)


def test_a_non_positive_radius_is_refused():
    document = cylinder(radius={"param": "wire"}, length={"param": "length"})
    with pytest.raises(EvaluationError, match="profile.radius"):
        molejo.evaluate(document, {"wire": 0.0, "length": 12.0})


# --- what this batch does not evaluate yet ---------------------------------


def test_an_unimplemented_primitive_names_itself():
    document = cylinder()
    document["path"] = [
        {"type": "spline", "points": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]}
    ]
    with pytest.raises(NotImplementedError) as caught:
        molejo.evaluate(document)
    message = str(caught.value)
    assert "spline" in message
    assert "path[0]" in message
    assert "not implemented" in message


def test_an_unimplemented_message_names_what_this_build_does_evaluate():
    document = cylinder()
    document["path"] = [
        {"type": "spline", "points": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]}
    ]
    with pytest.raises(NotImplementedError) as caught:
        molejo.evaluate(document)
    for name in ("line", "arc", "helix", "wrap"):
        assert f"'{name}'" in str(caught.value)


def test_a_closed_loop_of_a_chain_is_not_evaluated_yet():
    document = cylinder()
    document["loop"] = True
    with pytest.raises(NotImplementedError, match="loop"):
        molejo.evaluate(document)


def test_a_chained_path_spends_the_declared_segments_on_each_primitive():
    # The cylinder's own convention read against a chain: two lines at 4
    # segments each are 8 segments and 9 rings, and the joint ring is
    # sampled once. `test_curved_paths.py` is where chains are pinned.
    document = cylinder(path=4, profile=12)
    document["path"] = [
        {"type": "line", "to": [0.0, 0.0, 5.0]},
        {"type": "line", "to": [0.0, 0.0, 10.0]},
    ]
    mesh = molejo.evaluate(document)
    assert mesh.vertices.shape == (9 * 12 + 2, 3)


# --- package surface --------------------------------------------------------


def test_the_evaluation_surface_is_exported_from_the_package():
    for name in ["evaluate", "Mesh", "EvaluationError"]:
        assert hasattr(molejo, name), f"molejo.{name} is not exported"


def test_a_mesh_repr_states_its_size():
    mesh = molejo.evaluate(cylinder(path=4, profile=64))
    assert "322" in repr(mesh) and "640" in repr(mesh)
