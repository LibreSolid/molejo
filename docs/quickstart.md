# Quickstart

This walk-through authors a valve spring in Python, evaluates it to a
mesh and an STL, hands the spec to a browser, and animates it there.
Along the way it makes a toothed belt and a filament loom, because those
three are what molejo exists for.

## Author a spring

```python
from molejo import Shape, Circle, Helix, P

spring = Shape(
    profile=Circle(radius=1.0),
    path=[Helix(radius=6.0, turns=2.5, height=P.height)],
    path_samples=24, profile_samples=8,
)
```

A shape is a closed planar profile (here a circle of radius 1) swept
along a path (here a helix), sampled at a declared tessellation:
`path_samples` rings along the path, `profile_samples` vertices around
the profile.

`P.height` is a **parameter reference**. The spring's height is not a
number yet — it is a named slot that a consumer binds at evaluation.
Ask a shape what it needs:

```python
>>> spring.params
frozenset({'height'})
```

References are deliberately not expressions. `P.free_length - P.lift`
raises a `TypeError` telling you what to do instead: compute derived
values in ordinary Python, outside the spec, and bind the result.

```python
free_length, lift = 30.0, 8.0
mesh = spring.evaluate(height=free_length - lift)
```

## Evaluate to a mesh and an STL

```python
>>> mesh = spring.evaluate(height=30.0)
>>> mesh
Mesh(202 vertices, 400 faces)
>>> mesh.vertices.shape, mesh.faces.shape
((202, 3), (400, 3))
```

`vertices` is a float64 numpy array, `faces` an int32 one, and the mesh
is watertight by construction — a closed profile swept and capped
admits no hole. Binary STL is one call:

```python
with open("spring.stl", "wb") as out:
    out.write(mesh.to_stl())
```

Evaluate again at another height and you get the *same* 202 vertices in
the same order, moved. Tessellation is declared in the spec and never
adaptive, so parameter values move vertices and never renumber them —
which is what makes vertex correspondence across machine states free,
and what makes the browser side below cheap. See {doc}`concepts`.

## The spec is the model

```python
spec = spring.to_json()
```

```json
{
  "molejo": 1,
  "profile": {"type": "circle", "radius": 1.0},
  "path": [{"type": "helix", "radius": 6.0, "turns": 2.5,
            "height": {"param": "height"}}],
  "loop": false,
  "tessellation": {"path": 24, "profile": 8}
}
```

The Python constructors mirror this JSON one-to-one — there is no sugar
the document cannot express and nothing the document expresses that the
constructors cannot. Ship it to a file, a database, a WebSocket; parse
it back with `Shape.from_json`; or hand-write it and skip Python
entirely. The full format is in {doc}`spec`.

## Animate it in the browser

The JavaScript package evaluates the same document to buffers shaped
for a three.js `BufferGeometry`:

```js
import * as THREE from 'three';
import { evaluate } from 'molejo';

// First evaluation allocates the buffers and writes the index once.
const buffers = evaluate(spec, { height: 30.0 });

const geometry = new THREE.BufferGeometry();
geometry.setAttribute('position',
    new THREE.BufferAttribute(buffers.positions, 3));
geometry.setIndex(new THREE.BufferAttribute(buffers.index, 1));
geometry.computeVertexNormals();
```

Per frame, hand the buffers back and only the positions are refilled,
in place — the index is a function of the document alone and is not
touched:

```js
function animate(t) {
  evaluate(spec, { height: 30.0 - lift(t) }, buffers);
  geometry.attributes.position.needsUpdate = true;
  geometry.computeVertexNormals();
}
```

Both evaluators produce the same vertices in the same order (to
per-runtime tolerances pinned by shared fixtures), so what your build
pipeline tests is what your viewer shows. Details in {doc}`javascript`.

## A toothed belt

A belt is a `wrap`: a path around ordered circles, following their
external tangents. This one circulates around three pulleys — one of
them an idler whose position is itself a parameter — with a trapezoidal
tooth pattern driven by `travel`:

```python
from molejo import Shape, Polygon, Wrap, Teeth, P

belt = Shape(
    profile=Polygon([(-0.4, -3.0), (0.9, -3.0), (0.9, 3.0), (-0.4, 3.0)]),
    path=[Wrap(
        around=[
            {"center": (0.0, 0.0), "radius": 8.0},
            {"center": (30.0, P.idler), "radius": 3.0},
            {"center": (60.0, 0.0), "radius": 5.0},
        ],
        teeth=Teeth(pitch=2.5, height=0.75, count=6),
        phase=P.travel,
    )],
    path_samples=10, profile_samples=4,
    loop=True,
)

mesh = belt.evaluate(idler=40.0, travel=7.3)
```

Advance `travel` each frame and the teeth circulate around the loop;
move `idler` and the belt re-tensions around the new geometry, tooth
count unchanged. A wrap is closed by construction, so its document
declares `loop: true`, and it is the one primitive that stands alone in
its path.

## A filament loom

A loom that follows a print head is a `spline` whose last point is the
head:

```python
from molejo import Shape, Circle, Spline, P

loom = Shape(
    profile=Circle(radius=2.0),
    path=[Spline(
        points=[
            (0.0, 90.0, -35.0),
            (60.0, 170.0, -10.0),
            (P.head_x, P.head_y, P.head_z),
        ],
        start_tangent=(0.0, 1.0, 0.0),
        end_tangent=(0.0, 0.0, -1.0),
    )],
    path_samples=6, profile_samples=8,
)

mesh = loom.evaluate(head_x=95.0, head_y=215.0, head_z=-45.0)
```

Three parameters, one analytic shape — no sampled grid over X, Y and Z.
This is the case that motivates keeping the shape analytic and moving
the evaluation to where it is needed.

## Where next

- {doc}`spec` — the JSON document format, field by field.
- {doc}`python` — the full Python API: authoring, evaluation, errors.
- {doc}`javascript` — the browser evaluator and three.js integration.
- {doc}`brep` — exact OCCT solids for exact-shape test architectures.
- {doc}`concepts` — determinism, vertex correspondence, and parity.
