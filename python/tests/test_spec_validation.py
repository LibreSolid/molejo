# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Structural validation of the canonical document.

Validation is structural only: it needs no parameter values, and says
nothing about geometry. It answers one question -- is this a v1 molejo
document -- and when the answer is no it names the offending element.
"""

import pytest

from molejo.spec import SPEC_VERSION, SpecError, parameter_names, validate

from conftest import SPRING_DOCUMENT


def test_spec_version_is_one():
    assert SPEC_VERSION == 1


def test_the_canonical_spring_document_validates(spring_document):
    assert validate(spring_document) is None


def test_loop_is_optional_and_defaults_to_false(spring_document):
    del spring_document["loop"]
    assert validate(spring_document) is None


@pytest.mark.parametrize(
    "primitive",
    [
        {"type": "line", "to": [0.0, 0.0, 10.0]},
        {"type": "line", "to": [{"param": "x"}, 0.0, {"param": "z"}]},
        {
            "type": "arc",
            "center": [0.0, 0.0, 0.0],
            "axis": [0.0, 0.0, 1.0],
            "angle": {"param": "sweep"},
        },
        {"type": "helix", "radius": 14.0, "turns": 6.5, "height": 46.8},
        {"type": "spline", "points": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]},
    ],
    ids=["line", "line-params", "arc", "helix", "spline"],
)
def test_every_v1_primitive_validates(spring_document, primitive):
    spring_document["path"] = [primitive]
    assert validate(spring_document) is None


# A wrap is a closed loop and the only primitive of its path, so it can
# only be validated in a document that says so.


@pytest.mark.parametrize(
    "primitive",
    [
        {
            "type": "wrap",
            "around": [
                {"center": [0.0, 0.0], "radius": 5.1},
                {"center": [0.0, 210.0], "radius": 5.1},
            ],
        },
        {
            "type": "wrap",
            "around": [
                {"center": [0.0, 0.0], "radius": 5.1},
                {"center": [0.0, 210.0], "radius": 5.1},
            ],
            "teeth": {
                "pitch": 2.5,
                "height": 0.7,
                "flank": "trapezoid",
                "count": 180,
            },
            "anchor": {"span": 0, "at": {"param": "y"}},
        },
        {
            "type": "wrap",
            "around": [
                {"center": [0.0, 0.0], "radius": 5.1},
                {"center": [0.0, 210.0], "radius": 5.1},
                {"center": [80.0, {"param": "idler"}], "radius": 3.0},
            ],
            "phase": {"param": "travel"},
        },
    ],
    ids=["wrap", "wrap-teeth", "wrap-phase"],
)
def test_every_wrap_validates_in_a_looped_document(spring_document, primitive):
    spring_document["path"] = [primitive]
    spring_document["loop"] = True
    assert validate(spring_document) is None


def test_a_wrap_must_be_the_only_primitive_in_its_path(spring_document):
    spring_document["loop"] = True
    spring_document["path"] = [
        {"type": "line", "to": [0.0, 0.0, 10.0]},
        {
            "type": "wrap",
            "around": [
                {"center": [0.0, 0.0], "radius": 5.1},
                {"center": [0.0, 210.0], "radius": 5.1},
            ],
        },
    ]
    with pytest.raises(SpecError) as caught:
        validate(spring_document)
    assert "path[1]" in str(caught.value)
    assert "only primitive" in str(caught.value)


def test_a_wrap_document_must_declare_its_loop(spring_document):
    spring_document["path"] = [
        {
            "type": "wrap",
            "around": [
                {"center": [0.0, 0.0], "radius": 5.1},
                {"center": [0.0, 210.0], "radius": 5.1},
            ],
        }
    ]
    with pytest.raises(SpecError, match="loop"):
        validate(spring_document)


def test_a_wrap_takes_an_anchor_or_a_phase_and_not_both(spring_document):
    spring_document["loop"] = True
    spring_document["path"] = [
        {
            "type": "wrap",
            "around": [
                {"center": [0.0, 0.0], "radius": 5.1},
                {"center": [0.0, 210.0], "radius": 5.1},
            ],
            "anchor": {"span": 0, "at": 40.0},
            "phase": 1.0,
        }
    ]
    with pytest.raises(SpecError) as caught:
        validate(spring_document)
    assert "path[0]" in str(caught.value)
    assert "anchor" in str(caught.value) and "phase" in str(caught.value)


@pytest.mark.parametrize("span", [2, 7], ids=["just-past", "far-past"])
def test_an_anchor_span_must_be_one_the_wrap_has(spring_document, span):
    spring_document["loop"] = True
    spring_document["path"] = [
        {
            "type": "wrap",
            "around": [
                {"center": [0.0, 0.0], "radius": 5.1},
                {"center": [0.0, 210.0], "radius": 5.1},
            ],
            "anchor": {"span": span, "at": 40.0},
        }
    ]
    with pytest.raises(SpecError, match=r"path\[0\]\.anchor\.span"):
        validate(spring_document)


@pytest.mark.parametrize(
    "profile",
    [
        {"type": "circle", "radius": 2.0},
        {"type": "circle", "radius": {"param": "wire"}},
        {"type": "polygon", "points": [[-1.0, 0.0], [1.0, 0.0], [0.0, 1.5]]},
    ],
    ids=["circle", "circle-param", "polygon"],
)
def test_every_v1_profile_validates(spring_document, profile):
    spring_document["profile"] = profile
    if profile["type"] == "polygon":
        # A polygon is sampled at its own points, no more and no fewer.
        spring_document["tessellation"]["profile"] = len(profile["points"])
    assert validate(spring_document) is None


def test_a_polygon_is_sampled_at_its_own_points(spring_document):
    spring_document["profile"] = {
        "type": "polygon",
        "points": [[-1.0, 0.0], [1.0, 0.0], [0.0, 1.5]],
    }
    spring_document["tessellation"]["profile"] = 16
    with pytest.raises(SpecError) as caught:
        validate(spring_document)
    assert "tessellation.profile" in str(caught.value)
    assert "3" in str(caught.value)


def test_a_document_that_is_not_an_object_is_rejected():
    with pytest.raises(SpecError, match="spec"):
        validate([1, 2, 3])


def test_a_dangling_parameter_is_not_a_structural_error(spring_document):
    """`height` is bound at evaluation, not at validation."""
    assert validate(spring_document) is None
    assert parameter_names(spring_document) == frozenset({"height"})


def test_parameter_names_collects_every_reference():
    document = dict(
        SPRING_DOCUMENT,
        profile={"type": "polygon", "points": [[{"param": "w"}, 0.0], [1.0, 0.0], [0.0, {"param": "h"}]]},
        tessellation={"path": 240, "profile": 3},
        path=[
            {"type": "line", "to": [0.0, {"param": "y"}, 0.0]},
            {
                "type": "arc",
                "center": [{"param": "y"}, 0.0, 0.0],
                "axis": [0.0, 0.0, 1.0],
                "angle": {"param": "sweep"},
            },
        ],
    )
    assert parameter_names(document) == frozenset({"w", "h", "y", "sweep"})


def test_parameter_names_of_a_literal_document_is_empty(spring_document):
    spring_document["path"][0]["height"] = 46.8
    assert parameter_names(spring_document) == frozenset()


@pytest.mark.parametrize("bad", [True, False], ids=["true", "false"])
def test_a_boolean_is_not_a_number(spring_document, bad):
    spring_document["profile"]["radius"] = bad
    with pytest.raises(SpecError, match=r"profile\.radius"):
        validate(spring_document)


def test_a_non_finite_number_is_rejected(spring_document):
    spring_document["profile"]["radius"] = float("inf")
    with pytest.raises(SpecError, match=r"profile\.radius"):
        validate(spring_document)


def test_an_empty_parameter_name_is_rejected(spring_document):
    spring_document["profile"]["radius"] = {"param": ""}
    with pytest.raises(SpecError, match=r"profile\.radius"):
        validate(spring_document)


def test_validation_reports_the_first_offending_element_only(spring_document):
    spring_document["profile"] = {"type": "blob"}
    spring_document["path"] = [{"type": "squiggle"}]
    with pytest.raises(SpecError) as caught:
        validate(spring_document)
    assert "blob" in str(caught.value)


def test_spec_error_is_a_value_error():
    assert issubclass(SpecError, ValueError)
