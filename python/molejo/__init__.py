# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Analytic flexible parts for mechanical CAD.

A molejo shape is a serializable spec -- a planar profile swept along a
parametric path whose numeric slots may reference named scalar
parameters. This package is the Python side: the authoring layer that
writes the spec, and (soon) the evaluator that turns spec plus parameter
values into a deterministic triangle mesh.

    from molejo import Shape, Circle, Helix, P

    spring = Shape(
        profile=Circle(radius=2.0),
        path=[Helix(radius=14.0, turns=6.5, height=P.height)],
        path_samples=240, profile_samples=16,
    )
    spring.to_json()          # the spec -- what a browser gets

Spec version 1 is defined in :mod:`molejo.spec`. Mesh evaluation is not
implemented yet; see the repository's openspec/ records.
"""

from .authoring import (
    Arc,
    Circle,
    Helix,
    Line,
    P,
    ParamRef,
    Polygon,
    Shape,
    Spline,
    Teeth,
    Wrap,
)
from .spec import SPEC_VERSION, SpecError, parameter_names, validate

__author__ = "Luis Henrique Cassis Fagundes"
__email__ = "lhfagundes@gmail.com"
__version__ = "0.0.1.dev0"

__all__ = [
    "SPEC_VERSION",
    "Arc",
    "Circle",
    "Helix",
    "Line",
    "P",
    "ParamRef",
    "Polygon",
    "Shape",
    "SpecError",
    "Spline",
    "Teeth",
    "Wrap",
    "parameter_names",
    "validate",
]
