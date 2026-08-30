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

Full documentation: <https://molejo.readthedocs.io>

## What it looks like

Authoring is Python-first; the JSON spec is the representation it
serializes to:

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

Version 0.1.0, implementing spec version 1: profiles (circle, polygon)
and path primitives (line, arc, helix, spline, wrap). Both packages
parse and validate the document against shared fixtures; the Python
package also authors it (`Shape`, `Circle`, …, `P`).

Circle and polygon profiles swept along the whole v1 path vocabulary —
`line`, `arc`, `helix`, `spline` and `wrap` — evaluate in both runtimes,
singly or chained, capped or closed into a loop and watertight either
way, from Python as numpy arrays and binary STL, from JavaScript as
reusable three.js buffers, pinned to each other by shared parity
fixtures. The spring in the sample above is one of those fixtures rather
than a promise, and so are a toothed belt around three pulleys whose
teeth circulate with a parameter and a filament loom whose head follows
three. The one gap in the v1 vocabulary raises naming itself: closing a
loop that is not a wrap.

The B-rep evaluator installs with `pip install molejo[brep]` and
evaluates the same documents to closed OCCT solids —
`molejo.brep.evaluate(spec, values)` or `shape.brep(**values)` — with the
same refusals, word for word, as the mesh evaluator. Every parity fixture
is checked through it on volume and area. An install without the extra
imports and meshes and exports STL exactly as before; asking it for a
solid raises naming the extra.

molejo 0.1 has done real work before being called a release: it is the
flexible-part representation of [solid-node](https://github.com/LibreSolid/solid-node)
machine models, where its springs and belts hold up in animated,
geometrically tested engines and 3D printers (a V8 engine's valve
springs, a Metamaquina 2's drive belts) rather than only in this
repository's fixtures.

A package version carries the spec version it implements. Both packages
carry spec v1 at `0.1.0` and release together for a given spec version.
One document, two implementations: neither runtime is ever published
against a spec version the other has not caught up to.

Publishing to PyPI (`python/`) and npm (`js/`) is the maintainer's
explicit decision, never a side effect of building: `scripts/check-dist`,
the release dry-run, packs each package, installs it into a throwaway
environment outside this repository and evaluates a fixture there — and
uploads nothing.

## Origin

molejo was born from [solid-node](https://github.com/LibreSolid/solid-node),
a Python framework for mechanical CAD projects, which needed springs,
belts and cable looms in animated, testable machine models. solid-node
adapts molejo as one leaf-geometry technology among the several it
supports; molejo itself is independent and consumable by any Python or
three.js project.

## License

Apache License 2.0 — see `LICENSE`.
