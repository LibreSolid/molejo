# molejo

*The give in your machine.*

**molejo** (Brazilian Portuguese: the springy give of a thing) is an
analytic representation for the flexible parts of a machine — valve
springs, timing belts, cable looms, filament — parts whose *shape* is a
function of machine state, not just their placement.

A molejo shape is a serializable **spec**: a planar profile swept along
a parametric path, whose numeric slots may reference named scalar
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

Both mesh evaluators emit the same vertex count in the same order by
construction — tessellation is fixed and declared in the spec, never
curvature-adaptive — and are pinned to each other by shared parity
fixtures.

## A spring in five lines

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

## Where it comes from

molejo was born from [solid-node](https://github.com/LibreSolid/solid-node),
a Python framework for mechanical CAD projects, which needed springs,
belts and cable looms in animated, testable machine models. It has done
real work before being called a release: a V8 engine's valve springs
and a Metamaquina 2 3D printer's drive belts run on it. molejo itself
is independent and consumable by any Python or three.js project.

## Documentation

```{toctree}
:maxdepth: 2

installation
quickstart
spec
python
javascript
brep
concepts
api
changelog
```

## License

Apache License 2.0. Source and issue tracker:
[github.com/LibreSolid/molejo](https://github.com/LibreSolid/molejo).
