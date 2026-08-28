# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The shared parity fixtures, run against the Python evaluator.

`js/test/parity-fixtures.test.js` is this file's twin: same fixtures,
same discovery, same comparison, a tolerance chosen for its own runtime.
Between them they are what stops the two evaluators drifting apart, so
the comparison itself is held to account: `test_the_comparison_actually
_compares` feeds deliberately perturbed copies of every fixture through
the same code and demands that each one fail.

Counts and ordering are exact -- the same vertex index means the same
material point in both runtimes, or the whole fixed-tessellation design
buys nothing -- and coordinates match within the fixture's declared
tolerance, `|actual - expected| <= tolerance * (1 + |expected|)`.
"""

import copy

import numpy as np
import pytest

import molejo
from molejo.spec import parameter_names

from conftest import parity_files, parity_fixture, parity_manifest

FILES = parity_files()


# --- the comparison ---------------------------------------------------------


def compare(where, expected_vertices, expected_faces, mesh, tolerance):
    """Raise ``AssertionError`` unless the mesh matches the expectation.

    Named failures: the fixture, the case, and the first element that
    departs -- an evaluator that drifts should say where, not merely that.
    """
    expected_vertices = np.asarray(expected_vertices, dtype=np.float64)
    expected_faces = np.asarray(expected_faces, dtype=np.int64)

    if mesh.vertices.shape != expected_vertices.shape:
        raise AssertionError(
            f"{where}: expected {expected_vertices.shape[0]} vertices, "
            f"got {mesh.vertices.shape[0]}"
        )
    if mesh.faces.shape != expected_faces.shape:
        raise AssertionError(
            f"{where}: expected {expected_faces.shape[0]} faces, "
            f"got {mesh.faces.shape[0]}"
        )

    departures = np.argwhere(np.asarray(mesh.faces, dtype=np.int64) != expected_faces)
    if len(departures):
        face, corner = (int(index) for index in departures[0])
        raise AssertionError(
            f"{where}: face {face} corner {corner} is "
            f"{int(mesh.faces[face][corner])}, expected {int(expected_faces[face][corner])}"
        )

    delta = np.abs(mesh.vertices - expected_vertices)
    bound = tolerance * (1.0 + np.abs(expected_vertices))
    departures = np.argwhere(delta > bound)
    if len(departures):
        vertex, axis = (int(index) for index in departures[0])
        raise AssertionError(
            f"{where}: vertex {vertex} axis {axis} is "
            f"{float(mesh.vertices[vertex][axis])!r}, "
            f"expected {float(expected_vertices[vertex][axis])!r} "
            f"(off by {delta[vertex][axis]:.3e}, tolerance {bound[vertex][axis]:.3e})"
        )


def run_fixture(filename, fixture):
    """Every case of one fixture, compared. Raises on the first departure."""
    tolerance = fixture["tolerance"]["python"]
    for case in fixture["cases"]:
        mesh = molejo.evaluate(fixture["spec"], case["values"])
        compare(
            f"{filename} [{case['name']}]",
            case["vertices"],
            fixture["faces"],
            mesh,
            tolerance,
        )


# --- both suites run every fixture -----------------------------------------


def test_there_is_at_least_one_parity_fixture():
    assert FILES, "no parity fixtures found; the evaluators are pinned to nothing"


def test_the_manifest_and_the_directory_agree():
    # Neither suite keeps a list of its own, so a fixture added for one
    # runtime cannot be silently skipped by the other; it can only be
    # missing from the manifest, and then both suites say so.
    assert sorted(parity_manifest()) == FILES


@pytest.mark.parametrize("filename", FILES)
def test_a_parity_fixture_matches_the_python_evaluation(filename):
    run_fixture(filename, parity_fixture(filename))


@pytest.mark.parametrize("filename", FILES)
def test_a_fixture_binds_exactly_the_parameters_its_spec_references(filename):
    fixture = parity_fixture(filename)
    referenced = parameter_names(fixture["spec"])
    for case in fixture["cases"]:
        assert set(case["values"]) == set(referenced), case["name"]


@pytest.mark.parametrize("filename", FILES)
def test_a_fixture_declares_a_tolerance_for_both_runtimes(filename):
    tolerance = parity_fixture(filename)["tolerance"]
    assert set(tolerance) == {"python", "js"}
    assert tolerance["python"] > 0.0 and tolerance["js"] > 0.0
    # Single precision cannot hold float64: the JS side must be the looser
    # of the two, and honestly so.
    assert tolerance["js"] >= tolerance["python"]


@pytest.mark.parametrize("filename", FILES)
def test_a_fixture_carries_more_than_one_binding(filename):
    # One binding cannot show that the counts hold still while the
    # coordinates move, which is the property the fixtures exist to pin.
    assert len(parity_fixture(filename)["cases"]) >= 2


# --- the comparison is held to account -------------------------------------


@pytest.mark.parametrize("filename", FILES)
def test_a_perturbed_vertex_fails_the_comparison(filename):
    fixture = parity_fixture(filename)
    perturbed = copy.deepcopy(fixture)
    offset = 1.0 + 1000.0 * fixture["tolerance"]["python"]
    perturbed["cases"][0]["vertices"][7][1] += offset
    with pytest.raises(AssertionError) as caught:
        run_fixture(filename, perturbed)
    assert "vertex 7 axis 1" in str(caught.value)


@pytest.mark.parametrize("filename", FILES)
def test_a_perturbed_face_fails_the_comparison(filename):
    perturbed = parity_fixture(filename)
    perturbed["faces"][3][2] = 0
    with pytest.raises(AssertionError, match="face 3 corner 2"):
        run_fixture(filename, perturbed)


@pytest.mark.parametrize("filename", FILES)
def test_a_dropped_vertex_fails_the_comparison(filename):
    perturbed = parity_fixture(filename)
    del perturbed["cases"][0]["vertices"][0]
    with pytest.raises(AssertionError, match="vertices"):
        run_fixture(filename, perturbed)


@pytest.mark.parametrize("filename", FILES)
def test_a_dropped_face_fails_the_comparison(filename):
    perturbed = parity_fixture(filename)
    del perturbed["faces"][0]
    with pytest.raises(AssertionError, match="faces"):
        run_fixture(filename, perturbed)


@pytest.mark.parametrize("filename", FILES)
def test_a_perturbation_inside_tolerance_still_passes(filename):
    # The other half of the proof: a comparator that fails everything is
    # no better than one that passes everything.
    fixture = parity_fixture(filename)
    inside = fixture["tolerance"]["python"] / 2.0
    for case in fixture["cases"]:
        for vertex in case["vertices"]:
            vertex[0] += inside
    run_fixture(filename, fixture)
