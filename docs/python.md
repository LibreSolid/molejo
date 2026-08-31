# Python

The Python package is both sides of the coin: the **authoring layer**
that writes the spec and the **evaluator** that turns spec plus values
into a mesh. It depends on numpy alone; exact B-rep solids are the
optional extra described in {doc}`brep`.

```python
from molejo import Shape, Circle, Polygon, Line, Arc, Helix, Spline, Wrap, Teeth, P
```

## Authoring

The constructors mirror the JSON document one-to-one — there is no
sugar the document cannot express and nothing the document expresses
that the constructors cannot. That symmetry is what lets the JavaScript
side stay evaluation-only, and it means everything on the {doc}`spec`
page applies here verbatim; this page covers what is Python-specific.

```python
spring = Shape(
    profile=Circle(radius=2.0),
    path=[Helix(radius=14.0, turns=6.5, height=P.height)],
    path_samples=240, profile_samples=16,
)
```

`Shape` takes the profile, the path (a list of primitives), the two
tessellation counts (`path_samples`, `profile_samples`), and `loop`
(default `False`). The profile and primitive constructors are:

| Constructor | Spec element |
|---|---|
| `Circle(radius)` | `{"type": "circle", ...}` |
| `Polygon(points)` | `{"type": "polygon", ...}` — `points` an iterable of `(x, y)` |
| `Line(to)` | `{"type": "line", ...}` — `to` an `(x, y, z)` |
| `Arc(center, axis, angle)` | `{"type": "arc", ...}` |
| `Helix(radius, turns, height)` | `{"type": "helix", ...}` |
| `Spline(points, start_tangent=None, end_tangent=None)` | `{"type": "spline", ...}` |
| `Wrap(around, teeth=None, anchor=None, phase=None)` | `{"type": "wrap", ...}` — `around` a list of `{"center": (x, y), "radius": r}`, each optionally `"turn": "counterclockwise"` for a circle the belt is bent backwards over |
| `Teeth(pitch, height, count, flank="trapezoid", face="inner")` | a wrap's `teeth` object; `face="outer"` stands the teeth on the belt's outer face |

Any numeric slot accepts a number or a parameter reference.

### Parameters: `P`

`P.height` (or `P["height"]`, for names that are not identifiers) is a
{class}`~molejo.ParamRef` — a plain reference to a named scalar
parameter, bound at evaluation.

It is deliberately **not** an expression. Every arithmetic and
comparison operator is refused, so the authoring layer cannot grow an
expression language behind the spec's back:

```python
>>> P.free_length - P.lift
TypeError: molejo parameters are plain references, not expressions:
'free_length' cannot take part in arithmetic or comparison. Compute the
derived value in ordinary Python, outside the spec, and bind it at
evaluation (shape.evaluate(free_length=...)).
```

Derived values are ordinary Python at the call site:

```python
mesh = spring.evaluate(height=free_length - lift)
```

Ask a shape what it references:

```python
>>> spring.params
frozenset({'height'})
```

### Serialization

```python
document = spring.to_dict()     # the canonical document, validated
text = spring.to_json()         # the same, as JSON text (indent=2)

spring = Shape.from_dict(document)
spring = Shape.from_json(text)
```

`to_dict` validates what it emits and `from_dict`/`from_json` validate
what they read, so an invalid document can neither leave nor enter the
authoring layer. Round-tripping is exact.

## Evaluation

```python
mesh = spring.evaluate(height=46.8)
```

or, working from a document rather than a `Shape`:

```python
from molejo import evaluate

mesh = evaluate(document, {"height": 46.8})
```

The values mapping is plain `{name: number}`. Names the document does
not reference are **ignored**, so a consumer may hand over its whole
machine state; a name the document references and the mapping does not
bind raises {class}`~molejo.EvaluationError` naming both the parameter
and the slot. No partial or repaired mesh is ever returned: everything
a parameter can touch is resolved before a single vertex is written.

### `Mesh`

```python
>>> mesh
Mesh(3858 vertices, 7712 faces)
>>> mesh.vertices    # float64 numpy array, shape (V, 3)
>>> mesh.faces       # int32 numpy array, shape (F, 3), outward winding
```

The mesh is watertight by construction and deterministic: one document
and one binding always give the identical bytes. Vertex ordering is
part of the contract — see {doc}`concepts` for the layout.

### STL export

```python
data = mesh.to_stl()    # binary STL, bytes
```

Binary STL with outward-wound facets and normals computed from the
winding. Deterministic too: same document, same values, same bytes.

## Errors

Three kinds, for three questions:

- {class}`~molejo.SpecError` (a `ValueError`) — the document is not a
  valid spec. Raised at authoring or parse time, naming the
  offending element by its position in the document.
- {class}`~molejo.EvaluationError` (a `ValueError`) — the document is
  valid but cannot be evaluated at these values: an unbound or
  non-finite parameter, a line to nowhere, an arc with no radius, a
  wrap with no tangent between two of its circles. The message names
  the parameter or
  slot.
- `NotImplementedError` — valid spec vocabulary this build does not
  evaluate: `loop: true` on a path that is not a `wrap`. The message
  says exactly that.

The messages are byte-identical to the JavaScript evaluator's, so a
spec that fails in your pipeline fails with the same words in your
viewer.

The B-rep evaluator adds two of its own —
{class}`~molejo.brep.BrepUnavailable` and
{class}`~molejo.brep.BrepError` — described in {doc}`brep`.
