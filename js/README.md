# molejo

*The give in your machine.*

**molejo** (Brazilian Portuguese: the springy give of a thing) is an
analytic representation for the flexible parts of a machine — valve
springs, timing belts, cable looms, filament — parts whose *shape* is a
function of machine state, not just their placement.

A molejo shape is a serializable **spec**: a planar profile swept along a
parametric path, whose numeric slots may reference named scalar
parameters. This npm package is the browser (and Node) evaluator: it
turns a spec plus parameter values into vertex buffers for three.js,
cheap enough to re-evaluate every animation frame.

**Full documentation: <https://molejo.readthedocs.io>**

## Install

```sh
npm install molejo
```

Plain ES modules, no dependencies, no build step.

## Evaluation only

The npm package is the twin of the [Python
package](https://pypi.org/project/molejo/), which is where shapes are
authored. This side parses, validates and evaluates specs authored
elsewhere; there is no authoring layer, because the Python constructors
mirror the JSON one-to-one and a hand-written spec is exactly as good an
input as an authored one.

```js
import {
  parseSpec, validate, parameterNames, evaluate,
  SpecError, EvaluationError, NotImplementedError,
  SPEC_VERSION, VERSION,
} from 'molejo';

const spec = parseSpec(await (await fetch('spring.json')).text());
const buffers = evaluate(spec, { height: 46.8 });
```

`buffers` is shaped for three.js — `positions` (`Float32Array`,
ring-major), `index` (`Uint32Array`, outward winding), `vertexCount` and
`triangleCount`.

## Per-frame re-evaluation

Tessellation is declared in the spec, so vertex count, ordering and index
are a function of the document alone; parameter values move vertices and
never renumber them. Pass the previous frame's result back as the third
argument and only `positions` is refilled, in place — no allocation, and
the index is not touched:

```js
evaluate(spec, { height: 50.0 - lift(t) }, buffers);
geometry.attributes.position.needsUpdate = true;
```

See the [JavaScript
guide](https://molejo.readthedocs.io/en/latest/javascript.html) for the
complete three.js integration.

## Parity with Python

Both evaluators emit the same vertex count in the same order by
construction — tessellation is fixed and declared in the spec, never
curvature-adaptive — and are pinned to each other by shared parity
fixtures, down to identical error messages. What differs is only what the
runtime forces: positions are `Float32Array` because that is what a
`BufferGeometry` wants, so this side carries a looser (single-precision)
coordinate tolerance than the float64 Python side.

A spec version is the `MAJOR.MINOR` of the release that introduced it,
written as a JSON string: `0.1.0` carries spec `"0.1"`, `0.2.0` carries
spec `"0.2"`. Both packages release together for a given spec version;
neither runtime is ever published against a spec version the other has
not caught up to.

## Links

- Documentation — <https://molejo.readthedocs.io>
- Source — <https://github.com/LibreSolid/molejo>
- Python package — <https://pypi.org/project/molejo/>

## License

Apache License 2.0 — see `LICENSE`.
