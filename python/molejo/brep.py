# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Spec plus parameter values to an exact B-rep solid.

The same document the mesh evaluators read, evaluated without sampling
anything. A line is an edge, an arc is an edge on a circle, a helix is a
curve on a cylindrical surface, a spline is a cubic B-spline, and a wrap
is the chain of tangent lines and arcs its circles define. The profile is
the analytic profile the document declares -- a true circle, not the
M-gon ``tessellation.profile`` asks the mesh evaluator for -- because
``tessellation`` is a sampling instruction and this evaluation does not
sample.

That is what lets a consumer whose testing architecture asserts on exact
shapes use molejo at all, and it is why B-rep compatibility is an
admission rule for the vocabulary rather than a feature bolted on after
(see design.md, "B-rep compatibility is a vocabulary admission rule").

    from molejo.brep import evaluate

    result = evaluate(spring_document, {"height": 30.0})
    result.solid        # a TopoDS_Solid, closed
    result.tolerance    # the declared approximation tolerance
    result.volume()     # exact analytic properties, not facet sums

**Exactness is declared, not hoped for.** ``tolerance`` is ``0.0`` when
every surface of the result is analytic -- planes, cylinders, cones,
spheres and toroidal patches -- and :data:`APPROXIMATION` when some part
of the construction had no closed form OCCT can hold: the swept surface
along a helix or a spline, and the Archimedean spiral a belt's tooth ramp
traces where it crosses an arc. A zero-tolerance result is checked
against that claim before it is handed back, so the evaluator cannot
quietly degrade an analytically representable sweep and still call it
exact.

**OCCT is an optional extra.** The browser never needs it and a maker who
only wants meshes should not install a CAD kernel to get them, so
``molejo`` itself depends on numpy alone and this module's kernel lives
behind ``pip install molejo[brep]``. Importing this module always works;
evaluating without the extra raises :class:`BrepUnavailable`, naming it.
"""

__all__ = [
    "APPROXIMATION",
    "BrepError",
    "BrepResult",
    "BrepUnavailable",
    "evaluate",
]

#: The approximation tolerance this evaluator asks OCCT for wherever no
#: closed form exists, and the value a result declares when it used one.
#: Tightening it beyond this buys nothing measurable and costs build time;
#: loosening it would make the declaration a weaker promise than the
#: geometry actually keeps.
APPROXIMATION = 1e-6

_MISSING = (
    "molejo's B-rep evaluator needs OCCT, which the 'brep' extra installs: "
    "pip install molejo[brep]. Mesh evaluation and STL export need nothing "
    "beyond numpy, so an install without the extra is not broken -- it just "
    "has no exact shapes."
)


class BrepUnavailable(ImportError):
    """The `brep` extra is not installed, so there is no kernel to build with.

    An :class:`ImportError` on purpose: a caller that would rather fall
    back to a mesh should be able to catch this as the ordinary
    missing-dependency failure it is.
    """


class BrepError(RuntimeError):
    """The kernel produced something this evaluator will not vouch for.

    A shape that does not check out, a shell that is not closed, or a
    surface that is an approximation where the result claims exactness.
    Structural faults are :class:`molejo.spec.SpecError` and value faults
    are :class:`molejo.evaluator.EvaluationError`; this is the third kind,
    and it is never returned quietly.
    """


class BrepResult:
    """One closed solid, and the honest tolerance it was built to.

    ``solid`` is an OCCT ``TopoDS_Solid``: whatever a consumer's
    exact-shape machinery does with a solid, it can do with this one.
    ``tolerance`` is ``0.0`` for a fully analytic construction and
    :data:`APPROXIMATION` otherwise, so a caller can tell an exact
    assertion from a tolerant one without inspecting the geometry.
    """

    __slots__ = ("solid", "tolerance")

    def __init__(self, solid, tolerance):
        self.solid = solid
        self.tolerance = tolerance

    def __repr__(self):
        return (
            f"BrepResult({len(self.surfaces())} faces, "
            f"tolerance={self.tolerance!r})"
        )

    def volume(self):
        """The enclosed volume, integrated over the exact surfaces."""
        return _kernel().volume(self.solid)

    def area(self):
        """The total surface area, integrated over the exact surfaces."""
        return _kernel().area(self.solid)

    def surfaces(self):
        """Each face's surface class, in face order.

        Plain names -- ``"Plane"``, ``"Cylinder"``, ``"Torus"``,
        ``"BSplineSurface"`` -- so a caller can check what it was given
        without importing OCCT itself.
        """
        return _kernel().surfaces(self.solid)

    def is_closed(self):
        """Whether the solid is one valid, closed shell."""
        return _kernel().is_closed(self.solid)


#: The kernel module, imported on first use so that importing this module
#: never requires OCCT. Reset to ``None`` it will be looked up again, which
#: is what keeps one absent import from poisoning the process.
_KERNEL = None


def _kernel():
    """The OCCT-backed kernel, or an error naming the extra that carries it."""
    global _KERNEL
    if _KERNEL is None:
        # `import_module` rather than `from . import _occt`, which would
        # hand back a stale attribute of the package without ever asking
        # the import system whether OCCT is really there.
        from importlib import import_module

        try:
            _KERNEL = import_module("._occt", __package__)
        except ImportError as error:
            raise BrepUnavailable(_MISSING) from error
    return _KERNEL


def evaluate(document, values=None):
    """Evaluate a molejo document to an exact solid at the given values.

    ``values`` is the same plain ``{name: number}`` mapping the mesh
    evaluator takes, and the refusals are the same too: a dangling
    parameter, a non-numeric value, a line that goes nowhere, a wrap with
    no external tangent all raise
    :class:`molejo.evaluator.EvaluationError` with the identical message,
    because both evaluators resolve and refuse through the same code.
    """
    return _kernel().build(document, values)
