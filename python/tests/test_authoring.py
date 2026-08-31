# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The Python-first authoring layer.

Authors write shapes in Python; JSON is the representation both
evaluators consume. The two must agree exactly: a shape authored with
constructors serializes to the canonical document a hand-writer would
type, and parsing that document back reproduces the shape.
"""

import json
import operator

import pytest

import molejo
from molejo import Arc, Circle, Helix, Line, P, Polygon, Shape, Spline, Teeth, Wrap
from molejo.spec import SpecError

from conftest import SPRING_DOCUMENT


def spring():
    return Shape(
        profile=Circle(radius=2.0),
        path=[Helix(radius=14.0, turns=6.5, height=P.height)],
        path_samples=240,
        profile_samples=16,
    )


# --- the canonical document ------------------------------------------------


def test_authored_spring_serializes_to_the_canonical_document():
    assert spring().to_dict() == SPRING_DOCUMENT


def test_authored_spring_json_parses_to_the_canonical_document():
    assert json.loads(spring().to_json()) == SPRING_DOCUMENT


def test_the_canonical_document_round_trips_through_the_authoring_layer():
    assert Shape.from_dict(SPRING_DOCUMENT).to_dict() == SPRING_DOCUMENT


def test_a_shape_round_trips_through_json():
    original = spring()
    assert Shape.from_json(original.to_json()).to_dict() == original.to_dict()


def test_from_dict_does_not_mutate_or_alias_its_input():
    document = json.loads(json.dumps(SPRING_DOCUMENT))
    shape = Shape.from_dict(document)
    document["tessellation"]["path"] = 7
    assert shape.to_dict()["tessellation"]["path"] == 240


def test_from_dict_validates():
    with pytest.raises(SpecError, match="squiggle"):
        Shape.from_dict(
            {
                "molejo": "0.1",
                "profile": {"type": "circle", "radius": 2.0},
                "path": [{"type": "squiggle"}],
                "tessellation": {"path": 32, "profile": 16},
            }
        )


def test_from_json_rejects_text_that_is_not_json():
    with pytest.raises(SpecError):
        Shape.from_json("{not json")


def test_to_dict_always_declares_loop():
    assert spring().to_dict()["loop"] is False
    assert Shape(
        profile=Circle(radius=1.0),
        path=[Line(to=(0.0, 0.0, 10.0))],
        path_samples=8,
        profile_samples=8,
        loop=True,
    ).to_dict()["loop"] is True


def test_an_authored_shape_validates():
    from molejo.spec import validate

    assert validate(spring().to_dict()) is None


# --- the whole 0.1 vocabulary ----------------------------------------------


def test_every_constructor_round_trips():
    shape = Shape(
        profile=Polygon(points=[(-1.0, 0.0), (1.0, 0.0), (1.0, 1.5), (-1.0, P.h)]),
        path=[
            Line(to=(0.0, P.y, 0.0)),
            Arc(center=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0), angle=P.sweep),
            Helix(radius=14.0, turns=6.5, height=46.8),
            Spline(points=[(0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (P.x, P.y, P.z)]),
            Spline(
                points=[(4.0, 5.0, 6.0)],
                start_tangent=(0.0, 1.0, 0.0),
                end_tangent=(0.0, 0.0, P.aim),
            ),
        ],
        path_samples=720,
        profile_samples=4,
    )
    document = shape.to_dict()
    assert Shape.from_dict(document).to_dict() == document


def test_a_wrap_round_trips():
    # A wrap owns its whole path and closes it, so it is authored in a
    # looped shape of its own.
    shape = Shape(
        profile=Polygon(points=[(-0.4, -3.0), (0.9, -3.0), (0.9, 3.0), (-0.4, 3.0)]),
        path=[
            Wrap(
                around=[
                    dict(center=(0.0, 0.0), radius=5.1),
                    dict(center=(0.0, 210.0), radius=5.1),
                ],
                teeth=Teeth(pitch=2.5, height=0.7, flank="trapezoid", count=180),
                anchor=dict(span=0, at=P.y),
            )
        ],
        path_samples=720,
        profile_samples=4,
        loop=True,
    )
    document = shape.to_dict()
    assert Shape.from_dict(document).to_dict() == document
    assert document["path"][0] == {
        "type": "wrap",
        "around": [
            {"center": [0.0, 0.0], "radius": 5.1},
            {"center": [0.0, 210.0], "radius": 5.1},
        ],
        "teeth": {"pitch": 2.5, "height": 0.7, "flank": "trapezoid", "count": 180},
        "anchor": {"span": 0, "at": {"param": "y"}},
    }
    assert document["loop"] is True


def test_a_closed_toothed_belt_carries_a_phase():
    document = Shape(
        profile=Circle(radius=1.0),
        path=[
            Wrap(
                around=[
                    dict(center=(0.0, 0.0), radius=5.1),
                    dict(center=(0.0, 210.0), radius=5.1),
                ],
                phase=P.travel,
            )
        ],
        path_samples=360,
        profile_samples=8,
        loop=True,
    ).to_dict()
    assert document["path"][0]["phase"] == {"param": "travel"}
    assert "anchor" not in document["path"][0]
    assert "teeth" not in document["path"][0]


def test_optional_spline_tangents_are_omitted_when_unset():
    # An absent tangent is not a value the author could have written: it
    # means "leave the way you came" at the start and "along the final
    # chord" at the end, both of which follow parameter values.
    assert Spline(points=[(1.0, 2.0, 3.0)]).to_dict() == {
        "type": "spline",
        "points": [[1.0, 2.0, 3.0]],
    }


def test_a_clamped_spline_carries_both_its_tangents():
    document = Spline(
        points=[(0.0, 90.0, -35.0), (P.head_x, P.head_y, P.head_z)],
        start_tangent=(0.0, 1.0, 0.0),
        end_tangent=(0.0, 0.0, -1.0),
    ).to_dict()
    assert document == {
        "type": "spline",
        "points": [
            [0.0, 90.0, -35.0],
            [{"param": "head_x"}, {"param": "head_y"}, {"param": "head_z"}],
        ],
        "start_tangent": [0.0, 1.0, 0.0],
        "end_tangent": [0.0, 0.0, -1.0],
    }


def test_optional_wrap_fields_are_omitted_when_unset():
    document = Wrap(
        around=[
            dict(center=(0.0, 0.0), radius=5.1),
            dict(center=(0.0, 210.0), radius=5.1),
        ]
    ).to_dict()
    assert document == {
        "type": "wrap",
        "around": [
            {"center": [0.0, 0.0], "radius": 5.1},
            {"center": [0.0, 210.0], "radius": 5.1},
        ],
    }


def test_a_malformed_shape_is_rejected_when_it_serializes():
    with pytest.raises(SpecError, match="at least 3 points"):
        Shape(
            profile=Polygon(points=[(0.0, 0.0), (1.0, 0.0)]),
            path=[Line(to=(0.0, 0.0, 1.0))],
            path_samples=8,
            profile_samples=8,
        ).to_dict()


# --- parameters ------------------------------------------------------------


def test_params_reports_every_referenced_name():
    assert spring().params == frozenset({"height"})


def test_params_is_a_frozenset():
    assert isinstance(spring().params, frozenset)


def test_params_of_a_literal_shape_is_empty():
    shape = Shape(
        profile=Circle(radius=2.0),
        path=[Helix(radius=14.0, turns=6.5, height=46.8)],
        path_samples=240,
        profile_samples=16,
    )
    assert shape.params == frozenset()


def test_params_spans_profile_and_path():
    shape = Shape(
        profile=Circle(radius=P.wire),
        path=[Line(to=(P.x, P.y, P.z))],
        path_samples=8,
        profile_samples=8,
    )
    assert shape.params == frozenset({"wire", "x", "y", "z"})


def test_a_parameter_reference_carries_its_name():
    assert P.height.name == "height"


def test_parameter_references_compare_by_name():
    assert P.height == P.height
    assert P.height != P.lift


def test_a_parameter_reference_serializes_as_a_reference():
    assert P.height.to_dict() == {"param": "height"}


BINARY_OPERATORS = [
    operator.add,
    operator.sub,
    operator.mul,
    operator.truediv,
    operator.floordiv,
    operator.mod,
    operator.pow,
    operator.lt,
    operator.le,
    operator.gt,
    operator.ge,
]


@pytest.mark.parametrize("op", BINARY_OPERATORS, ids=lambda op: op.__name__)
def test_a_parameter_reference_refuses_arithmetic(op):
    with pytest.raises(TypeError) as caught:
        op(P.free_length, P.lift)
    assert "molejo parameters are plain references" in str(caught.value)


@pytest.mark.parametrize("op", BINARY_OPERATORS, ids=lambda op: op.__name__)
def test_a_parameter_reference_refuses_arithmetic_with_a_number(op):
    with pytest.raises(TypeError, match="molejo parameters are plain references"):
        op(P.free_length, 3.0)
    with pytest.raises(TypeError, match="molejo parameters are plain references"):
        op(3.0, P.free_length)


@pytest.mark.parametrize(
    "op", [operator.neg, operator.pos, abs, float, int, round],
    ids=["neg", "pos", "abs", "float", "int", "round"],
)
def test_a_parameter_reference_refuses_unary_coercion(op):
    with pytest.raises(TypeError, match="molejo parameters are plain references"):
        op(P.lift)


def test_the_refusal_tells_the_author_what_to_do_instead():
    with pytest.raises(TypeError) as caught:
        P.free_length - P.lift
    message = str(caught.value)
    assert "free_length" in message
    assert "outside the spec" in message


def test_a_parameter_reference_is_not_a_dunder_factory():
    with pytest.raises(AttributeError):
        P.__wrapped__


# --- authoring meets evaluation --------------------------------------------


def test_an_authored_shape_and_its_document_evaluate_identically():
    shape = Shape(
        profile=Circle(radius=2.0),
        path=[Line(to=(0.0, 0.0, P.height))],
        path_samples=8,
        profile_samples=16,
    )
    authored = shape.evaluate(height=46.8)
    parsed = molejo.evaluate(json.loads(shape.to_json()), {"height": 46.8})
    assert authored.vertices.tobytes() == parsed.vertices.tobytes()
    assert authored.faces.tobytes() == parsed.faces.tobytes()


def test_an_authored_loom_evaluates():
    # The last primitive of the 0.1 vocabulary to arrive: an authored
    # spline is an evaluation like any other.
    loom = Shape(
        profile=Circle(radius=2.0),
        path=[
            Spline(
                points=[(0.0, 90.0, -35.0), (P.head_x, P.head_y, P.head_z)],
                start_tangent=(0.0, 1.0, 0.0),
                end_tangent=(0.0, 0.0, -1.0),
            )
        ],
        path_samples=8,
        profile_samples=16,
    )
    mesh = loom.evaluate(head_x=95.0, head_y=215.0, head_z=-45.0)
    assert mesh.vertices.shape == (17 * 16 + 2, 3)


def test_the_canonical_spring_evaluates():
    # The shape the README advertises, at the resolution it declares.
    mesh = spring().evaluate(height=46.8)
    assert mesh.vertices.shape == (241 * 16 + 2, 3)


# --- package surface -------------------------------------------------------


def test_the_authoring_vocabulary_is_exported_from_the_package():
    for name in [
        "Shape",
        "Circle",
        "Polygon",
        "Line",
        "Arc",
        "Helix",
        "Spline",
        "Wrap",
        "Teeth",
        "P",
        "SpecError",
    ]:
        assert hasattr(molejo, name), f"molejo.{name} is not exported"
