# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Spec plus parameter values to a triangle mesh.

The evaluator's surface, ahead of its arithmetic: the tests in
``python/tests/test_evaluation.py`` and ``python/tests/test_stl.py``
describe the cylinder slice this module owes them, and every one of them
is red against this file.
"""

__all__ = ["EvaluationError", "Mesh", "evaluate"]


class EvaluationError(ValueError):
    """A spec cannot be evaluated at the given parameter values.

    The message names the offending element -- the parameter, the slot it
    is referenced from -- so a caller can bind what is missing. Structural
    faults are :class:`molejo.spec.SpecError`; this is what only values
    can reveal.
    """


class Mesh:
    """A triangle mesh: float64 vertices ``(V, 3)``, integer faces ``(F, 3)``."""

    __slots__ = ("vertices", "faces")

    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces

    def to_stl(self):
        """The mesh as binary STL bytes."""
        raise NotImplementedError("molejo evaluation is not implemented yet")


def evaluate(document, values=None):
    """Evaluate a molejo document at the given parameter values."""
    raise NotImplementedError("molejo evaluation is not implemented yet")
