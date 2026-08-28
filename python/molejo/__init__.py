# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Analytic flexible parts for mechanical CAD.

A molejo shape is a serializable spec -- a planar profile swept along a
parametric path whose numeric slots may reference named scalar
parameters. This package is the Python side: the authoring layer that
writes the spec, and the evaluator that turns spec plus parameter values
into a deterministic triangle mesh.

    from molejo import Shape, Circle, Line, P

    tube = Shape(
        profile=Circle(radius=2.0),
        path=[Line(to=(0.0, 0.0, P.length))],
        path_samples=8, profile_samples=32,
    )
    tube.to_json()            # the spec -- what a browser gets
    mesh = tube.evaluate(length=46.8)   # numpy vertices and faces
    mesh.to_stl()             # binary STL bytes

Spec version 1 is defined in :mod:`molejo.spec` and evaluated in
:mod:`molejo.evaluator`, which currently sweeps a circle profile along a
single line; every other primitive raises naming itself. See the
repository's openspec/ records.
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
from .evaluator import EvaluationError, Mesh, evaluate
from .spec import SPEC_VERSION, SpecError, parameter_names, validate

__author__ = "Luis Henrique Cassis Fagundes"
__email__ = "lhfagundes@gmail.com"
__version__ = "0.0.1.dev0"

__all__ = [
    "SPEC_VERSION",
    "Arc",
    "Circle",
    "EvaluationError",
    "Helix",
    "Line",
    "Mesh",
    "P",
    "ParamRef",
    "Polygon",
    "Shape",
    "SpecError",
    "Spline",
    "Teeth",
    "Wrap",
    "evaluate",
    "parameter_names",
    "validate",
]
