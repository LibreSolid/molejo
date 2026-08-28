# molejo

*The give in your machine.*

**molejo** (Brazilian Portuguese: the springy give of a thing) is an
analytic representation for the flexible parts of a machine — valve
springs, timing belts, cable looms, filament — parts whose *shape* is a
function of machine state, not just their placement.

A molejo shape is a serializable **spec**: a planar profile swept along a
parametric path, whose numeric slots may reference named scalar
parameters. The spec is the model. Meshes are evaluations of it:

- the **Python evaluator** turns a spec plus parameter values into an
  exact triangle mesh (and STL) for build pipelines, geometric tests,
  and collision checks;
- the **JavaScript evaluator** turns the same spec plus the same values
  into vertex buffers for three.js, cheap enough to re-evaluate every
  animation frame;
- an optional **B-rep evaluator** (OCCT, via the `brep` extra of the
  Python package) turns the same spec plus the same values into an
  exact solid, for testing architectures that assert on exact shapes.

Both evaluators emit the same vertex count in the same order by
construction — tessellation is fixed and declared in the spec, never
curvature-adaptive — and are pinned to each other by shared parity
fixtures.

## What it looks like

Authoring is Python-first; the JSON spec is the representation it
serializes to (API sketch — pre-alpha, see `openspec/changes/`):

```python
from molejo import Shape, Circle, Helix, P

spring = Shape(
    profile=Circle(radius=2.0),
    path=[Helix(radius=14.0, turns=6.5, height=P.height)],
    path_samples=240, profile_samples=16,
)

mesh = spring.evaluate(height=46.8)   # numpy vertices and faces
spring.to_json()                      # the spec — what a browser gets
```

`P.height` is a plain reference, not an expression: derived values
(`free_length - lift`) are computed in ordinary Python and bound at
evaluation. The browser side consumes the serialized spec only:

```js
import { evaluate } from 'molejo';
evaluate(spec, { height: 50.0 - lift(t) }, buffers); // per frame, in place
```

## Why

CAD kernels represent rigid geometry; animation systems interpolate
placement. A compressing spring, a circulating belt, or a cable loom
following a print head falls between the two: its geometry at any
instant is exact, closed-form math over a few scalars (a lift, a
carriage position), but no kernel evaluates that math in both a build
pipeline and a browser at frame rate.

Sampling the shape (morph targets, frame swapping) works for one
parameter and dies combinatorially at two or three — a loom that follows
X, Y and Z would need a sampled grid over all of them. molejo instead
keeps the shape analytic and moves the *evaluation* to wherever it is
needed.

## Design properties

- **Analytic master, evaluations on demand.** The spec defines exact
  curves and surfaces; every mesh is a deterministic sampling of them
  at the declared resolution, and the B-rep evaluator constructs the
  same curves exactly in OCCT. Line- and arc-based sweeps (belts) are
  analytic surfaces; helix and spline sweeps are tolerance-declared
  B-spline surfaces, as in any kernel.
- **Sweeps only, no booleans.** A closed profile swept along a path is
  watertight by construction; there is no repair pass because no input
  can be broken. Boolean interaction belongs to whatever mesh machinery
  consumes the evaluation.
- **Parameters are plain named numbers.** molejo does not know where
  they come from — a slider, a kinematic expression, a test instant.
  Expression languages belong to the consumer.
- **Continuity and self-intersection are the author's obligation.** The
  representation does not police an over-compressed spring; the
  consumer's tests can.

## Status

Pre-alpha. Spec version 1 — profiles (circle, polygon) and path
primitives (line, arc, helix, wrap, spline) — is under design; see
`openspec/changes/`. Nothing is published yet; `molejo` on PyPI
(`python/`) and npm (`js/`) is reserved for this project.

## Origin

molejo was born from [solid-node](https://github.com/LibreSolid/solid-node),
a Python framework for mechanical CAD projects, which needed springs,
belts and cable looms in animated, testable machine models. solid-node
adapts molejo as one leaf-geometry technology among the several it
supports; molejo itself is independent and consumable by any Python or
three.js project.

## License

Apache License 2.0 — see `LICENSE`.
