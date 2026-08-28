# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""What an installed molejo wheel must do, run from outside the repository.

`scripts/check-dist-python` copies this file into a throwaway directory and
runs it there with a throwaway venv's interpreter, so nothing here can
reach the source tree: an import that succeeds is the installed package,
not the checkout. The fixture arrives as an argument for the same reason --
the parity fixtures are repository data, deliberately not shipped in the
wheel, so a consumer's copy of molejo has no fixtures to fall back on.

Usage: python dist-smoke.py <cylinder-fixture.json>
"""

import json
import sys
from pathlib import Path

import molejo
from molejo import Circle, Helix, P, Shape


def check(condition, message):
    if not condition:
        raise SystemExit(f"dist-smoke: {message}")


def report(line):
    print(f"  {line}")


# --- the installed package, not the checkout --------------------------------

installed = Path(molejo.__file__).resolve().parent
check(
    "site-packages" in installed.parts,
    f"imported molejo from {installed}, which is not an installed package",
)
report(f"molejo {molejo.__version__} imported from {installed}")

# The fixtures are repository data. A wheel that shipped them would invite a
# consumer to depend on paths that are not part of the package's promise.
strays = sorted(
    path.name
    for path in installed.rglob("*")
    if path.is_file() and path.suffix == ".json"
)
check(not strays, f"the installed package carries data files: {strays}")
report("no fixtures or stray data inside the installed package")


# --- authoring: the README's spring, round-tripped --------------------------

spring = Shape(
    profile=Circle(radius=2.0),
    path=[Helix(radius=14.0, turns=6.5, height=P.height)],
    path_samples=240,
    profile_samples=16,
)
check(spring.params == {"height"}, f"spring parameters are {spring.params}")

text = spring.to_json()
reparsed = Shape.from_json(text)
check(
    reparsed.to_dict() == spring.to_dict(),
    "the spring does not survive to_json/from_json unchanged",
)
check(
    reparsed.to_json() == text,
    "the round-tripped spring does not re-serialize identically",
)
report(f"README spring authored and round-tripped ({len(text)} bytes of JSON)")

spring_mesh = spring.evaluate(height=46.8)
check(
    spring_mesh.vertices.shape == (241 * 16 + 2, 3),
    f"the spring evaluated to {spring_mesh.vertices.shape[0]} vertices",
)
report(f"spring evaluated at height=46.8: {spring_mesh.vertices.shape[0]} vertices")


# --- the cylinder parity fixture, from the repository -----------------------

check(len(sys.argv) == 2, "usage: dist-smoke.py <cylinder-fixture.json>")
fixture = json.loads(Path(sys.argv[1]).read_text())
tolerance = fixture["tolerance"]["python"]

margin = 0.0
for case in fixture["cases"]:
    mesh = molejo.evaluate(fixture["spec"], case["values"])
    expected = case["vertices"]
    check(
        mesh.vertices.shape[0] == len(expected),
        f"{case['name']}: {mesh.vertices.shape[0]} vertices, "
        f"expected {len(expected)}",
    )
    check(
        [list(face) for face in mesh.faces.tolist()] == fixture["faces"],
        f"{case['name']}: the face index departs from the fixture",
    )
    for index, (actual, wanted) in enumerate(zip(mesh.vertices.tolist(), expected)):
        for axis in range(3):
            relative = abs(actual[axis] - wanted[axis]) / (1.0 + abs(wanted[axis]))
            margin = max(margin, relative)
            check(
                relative <= tolerance,
                f"{case['name']}: vertex {index} axis {axis} is {actual[axis]}, "
                f"expected {wanted[axis]} (margin {relative:g} > {tolerance:g})",
            )

report(
    f"cylinder fixture matched over {len(fixture['cases'])} cases: "
    f"worst margin {margin:g}, tolerance {tolerance:g}"
)


# --- STL export -------------------------------------------------------------

stl = mesh.to_stl()
faces = len(fixture["faces"])
check(isinstance(stl, bytes), f"to_stl() returned {type(stl).__name__}, not bytes")
check(
    len(stl) == 84 + 50 * faces,
    f"binary STL is {len(stl)} bytes, expected {84 + 50 * faces} for {faces} facets",
)
check(
    int.from_bytes(stl[80:84], "little") == faces,
    "the STL facet count does not match the mesh",
)
report(f"binary STL exported: {len(stl)} bytes, {faces} facets")


# --- the B-rep extra is absent, and says so ---------------------------------

import molejo.brep  # noqa: E402  -- importing it must work without the extra

try:
    molejo.brep.evaluate(fixture["spec"], fixture["cases"][0]["values"])
except ImportError as error:
    message = str(error)
    raised = type(error)
else:
    raise SystemExit("dist-smoke: molejo.brep evaluated without the brep extra")

check(
    "molejo[brep]" in message,
    f"the refusal does not name the extra to install: {message}",
)
check(
    issubclass(raised, molejo.brep.BrepUnavailable),
    f"the refusal is {raised.__name__}, not BrepUnavailable",
)

try:
    spring.brep(height=46.8)
except molejo.brep.BrepUnavailable as second:
    check(
        str(second) == message,
        "shape.brep() and molejo.brep.evaluate() refuse differently",
    )
else:
    raise SystemExit("dist-smoke: shape.brep() evaluated without the brep extra")

report("without the extra, a solid is refused by name: pip install molejo[brep]")

print("dist-smoke: the installed wheel authors, evaluates, exports and refuses.")
