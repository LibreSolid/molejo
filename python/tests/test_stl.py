# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Binary STL export, read back by an independent parser.

The reader below is written from the binary STL format rather than from
molejo's writer: 80 header bytes, a little-endian triangle count, then
50 bytes per facet (a normal, three vertices, an attribute word). It
knows nothing about rings, caps, or vertex indices -- it welds a
triangle soup by coordinate and asks the two questions that matter of
any exported solid: is the surface closed, and does it enclose the
volume the shape claims.
"""

import math
import struct
from collections import Counter

import pytest

import molejo
from test_evaluation import chord_deficit, cylinder, prism_volume

# --- an independent binary STL reader --------------------------------------

HEADER_BYTES = 80
FACET_BYTES = 50


def read_binary_stl(data):
    """Every facet of a binary STL as (normal, (v0, v1, v2)) float triples."""
    assert len(data) >= HEADER_BYTES + 4, "an STL is at least a header and a count"
    assert not data[:5].lower().startswith(b"solid"), (
        "a binary STL must not open with 'solid': readers would take it for ASCII"
    )
    (count,) = struct.unpack_from("<I", data, HEADER_BYTES)
    expected = HEADER_BYTES + 4 + count * FACET_BYTES
    assert len(data) == expected, f"{count} facets need {expected} bytes, got {len(data)}"

    facets = []
    for index in range(count):
        offset = HEADER_BYTES + 4 + index * FACET_BYTES
        numbers = struct.unpack_from("<12f", data, offset)
        (attribute,) = struct.unpack_from("<H", data, offset + 48)
        assert attribute == 0, f"facet {index} carries a non-zero attribute word"
        facets.append((numbers[0:3], (numbers[3:6], numbers[6:9], numbers[9:12])))
    return facets


def weld(facets):
    """The triangle soup as indices into the distinct coordinates it uses."""
    indices = {}
    triangles = []
    for _normal, corners in facets:
        triangle = []
        for corner in corners:
            triangle.append(indices.setdefault(corner, len(indices)))
        triangles.append(tuple(triangle))
    return triangles, list(indices)


def watertight_failures(triangles):
    counts = Counter()
    for a, b, c in triangles:
        counts[(a, b)] += 1
        counts[(b, c)] += 1
        counts[(c, a)] += 1
    failures = []
    for edge, count in counts.items():
        if count != 1:
            failures.append(f"directed edge {edge} used {count} times")
        if counts[(edge[1], edge[0])] != 1:
            failures.append(f"edge {edge} is not matched by its opposite")
    return failures


def enclosed_volume(triangles, points):
    total = 0.0
    for a, b, c in triangles:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = points[a], points[b], points[c]
        total += (
            ax * (by * cz - bz * cy)
            + ay * (bz * cx - bx * cz)
            + az * (bx * cy - by * cx)
        )
    return total / 6.0


# --- the export -------------------------------------------------------------

RADIUS, LENGTH, PATH, PROFILE = 5.0, 12.0, 4, 64


def exported():
    mesh = molejo.evaluate(cylinder(RADIUS, LENGTH, PATH, PROFILE))
    return mesh, read_binary_stl(mesh.to_stl())


def test_the_stl_carries_every_triangle_of_the_evaluation():
    mesh, facets = exported()
    assert len(facets) == len(mesh.faces)


def test_the_exported_solid_is_watertight():
    _mesh, facets = exported()
    triangles, _points = weld(facets)
    assert watertight_failures(triangles) == []


def test_the_exported_solid_welds_to_the_evaluated_vertex_count():
    mesh, facets = exported()
    _triangles, points = weld(facets)
    assert len(points) == len(mesh.vertices)


def test_the_exported_volume_matches_the_analytic_volume():
    _mesh, facets = exported()
    triangles, points = weld(facets)
    volume = enclosed_volume(triangles, points)
    assert volume == pytest.approx(prism_volume(RADIUS, LENGTH, PROFILE), rel=1e-5)
    analytic = math.pi * RADIUS * RADIUS * LENGTH
    assert volume == pytest.approx(analytic, rel=2 * chord_deficit(PROFILE))


def test_the_facet_normals_point_outward():
    _mesh, facets = exported()
    centre = (0.0, 0.0, LENGTH / 2.0)
    for index, (normal, corners) in enumerate(facets):
        middle = [sum(axis) / 3.0 for axis in zip(*corners)]
        outward = [middle[axis] - centre[axis] for axis in range(3)]
        assert sum(n * o for n, o in zip(normal, outward)) > 0.0, f"facet {index}"
        assert math.isclose(math.sqrt(sum(n * n for n in normal)), 1.0, rel_tol=1e-5)


def test_the_export_is_deterministic():
    mesh = molejo.evaluate(cylinder(RADIUS, LENGTH, PATH, PROFILE))
    assert mesh.to_stl() == mesh.to_stl()


def test_the_export_names_molejo_in_its_header():
    mesh = molejo.evaluate(cylinder())
    header = mesh.to_stl()[:HEADER_BYTES]
    assert b"molejo" in header
    assert len(header) == HEADER_BYTES


def test_a_parameter_bound_shape_exports_the_shape_it_was_bound_to():
    document = cylinder(RADIUS, {"param": "length"}, PATH, PROFILE)
    mesh = molejo.evaluate(document, {"length": 30.0})
    triangles, points = weld(read_binary_stl(mesh.to_stl()))
    assert enclosed_volume(triangles, points) == pytest.approx(
        prism_volume(RADIUS, 30.0, PROFILE), rel=1e-5
    )
