# Exact solids (B-rep)

Some testing architectures do not want a mesh at all: they assert on
exact shapes — volumes, areas, surface classes — through a CAD kernel.
The B-rep evaluator serves them: **the same document, the same values,
evaluated without sampling anything** to a closed OCCT solid.

A line becomes an edge; an arc, an edge on a circle; a helix, a curve
on its cylindrical surface; a spline, a cubic B-spline; a wrap, the
chain of tangent lines and arcs its circles define. The profile is the
analytic profile the document declares — a true circle, not the M-gon
the mesh evaluators sample — because `tessellation` is a sampling
instruction and this evaluation does not sample.

## Installing

```console
$ pip install "molejo[brep]"
```

The extra brings in the OCCT kernel (`cadquery-ocp`). The browser never
needs it and a maker who only wants meshes should not install a CAD
kernel to get them, so `molejo` itself stays numpy-only. Importing
{mod}`molejo.brep` always works; *evaluating* without the extra raises
{class}`~molejo.brep.BrepUnavailable` — an `ImportError`, so a caller
that would rather fall back to a mesh can catch it as the ordinary
missing-dependency failure it is.

## Evaluating

```python
from molejo.brep import evaluate

result = evaluate(document, {"height": 30.0})
```

or, from a `Shape`:

```python
result = spring.brep(height=30.0)
```

The refusals are the mesh evaluator's, word for word: a dangling
parameter, a non-numeric value, a line that goes nowhere, a wrap with
no tangent between two of its circles all raise
{class}`~molejo.EvaluationError` with the
identical message, because both evaluators resolve and refuse through
the same code.

## `BrepResult`

```python
result.solid        # an OCCT TopoDS_Solid, closed
result.tolerance    # the declared approximation tolerance
result.volume()     # exact analytic properties, not facet sums
result.area()
result.surfaces()   # each face's surface class: "Plane", "Cylinder", ...
result.is_closed()  # one valid, closed shell
```

`solid` is a plain `TopoDS_Solid`: whatever a consumer's exact-shape
machinery does with a solid, it can do with this one. `surfaces()`
returns plain string names so a caller can check what it was given
without importing OCCT itself.

## Exactness is declared, not hoped for

`tolerance` is `0.0` when every surface of the result is analytic —
planes, cylinders, cones, spheres and toroidal patches — and `1e-6`
({data}`molejo.brep.APPROXIMATION`) when some part of the construction
had no closed form OCCT can hold: the swept surface along a helix or a
spline, and the Archimedean spiral a belt's tooth ramp traces where it
crosses an arc. Line- and arc-based sweeps (belts without teeth) are
fully analytic.

A zero-tolerance result is checked against that claim before it is
handed back, so the evaluator cannot quietly degrade an analytically
representable sweep and still call it exact. A caller can therefore
tell an exact assertion from a tolerant one by reading `tolerance`,
without inspecting the geometry.

If the kernel produces something the evaluator will not vouch for — a
shape that does not check out, a shell that is not closed, an
approximation where the result claims exactness —
{class}`~molejo.brep.BrepError` is raised; nothing questionable is ever
returned quietly.

## How it stays honest

Every parity fixture in the repository is evaluated through the B-rep
evaluator and checked on volume and area against both the mesh arrays
and an independently written closed form (at 1e-6). B-rep compatibility
is an *admission rule* for the spec vocabulary rather than a feature
bolted on after: a primitive that could not be constructed exactly
would not have entered spec 0.1.
