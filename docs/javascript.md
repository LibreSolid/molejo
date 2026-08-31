# JavaScript

The npm package is the browser (and Node) twin of the Python evaluator:
**evaluation-only**. It parses, validates and evaluates specs authored
elsewhere; there is no authoring layer, because the Python constructors
mirror the JSON one-to-one and a hand-written spec is exactly as good
an input as an authored one.

Plain ES modules, no dependencies, no build step.

```js
import {
  parseSpec, validate, parameterNames, evaluate,
  SpecError, EvaluationError, NotImplementedError,
  SPEC_VERSION, VERSION,
} from 'molejo';
```

## Parsing and validation

```js
const spec = parseSpec(source);   // JSON text or an already parsed object
```

`parseSpec` validates and returns the document with `loop` made
explicit; the caller's object is not modified. `validate(document)`
does the checking alone, and `parameterNames(document)` returns the
`Set` of parameter names the document references, so a viewer can build
its bindings before the first frame.

An invalid document throws `SpecError` naming the offending element by
its position (`path[1].to[2]`) — with the same message, byte for byte,
that the Python validator raises.

## Evaluation

```js
const buffers = evaluate(spec, { height: 46.8 });
```

`values` is a plain `{name: number}` object. Names the spec does not
reference are ignored — hand over your whole machine state; a
referenced name left unbound throws `EvaluationError` naming the
parameter and the slot. No partial output is ever written.

The result is an object shaped for three.js:

```js
{
  positions: Float32Array,   // vertexCount * 3, ring-major
  index: Uint32Array,        // triangleCount * 3, outward winding
  vertexCount: Number,
  triangleCount: Number,
}
```

## Per-frame re-evaluation

Tessellation is declared in the spec, so the vertex count, ordering and
index are a function of the document alone; parameter values move
vertices and never renumber them. Pass the previous frame's result back
as the third argument and only `positions` is refilled, in place — no
allocation, and the index is not touched:

```js
evaluate(spec, { height: 50.0 - lift(t) }, buffers);
```

The buffers are checked against the spec before writing (a
`Float32Array`/`Uint32Array` of the wrong length is refused with an
`EvaluationError`), so reuse across *different* documents fails loudly
rather than corrupting a frame.

## three.js integration

molejo does not import three.js; the buffers are plain typed arrays
that a `BufferGeometry` consumes directly:

```js
import * as THREE from 'three';
import { evaluate, parseSpec } from 'molejo';

const spec = parseSpec(await (await fetch('spring.json')).text());
const buffers = evaluate(spec, { height: 30.0 });

const geometry = new THREE.BufferGeometry();
geometry.setAttribute('position',
    new THREE.BufferAttribute(buffers.positions, 3));
geometry.setIndex(new THREE.BufferAttribute(buffers.index, 1));
geometry.computeVertexNormals();

const mesh = new THREE.Mesh(geometry,
    new THREE.MeshStandardMaterial({ color: 0x8888ff }));
scene.add(mesh);

function animate(t) {
  evaluate(spec, { height: 30.0 - lift(t) }, buffers);
  geometry.attributes.position.needsUpdate = true;
  geometry.computeVertexNormals();
  renderer.render(scene, camera);
}
```

Remember that a molejo path always starts at the origin with tangent
+Z: place the mesh in your machine with the ordinary three.js
transform (`mesh.position`, `mesh.quaternion`), which is the consumer's
job by design.

## Parity with Python

The evaluator is held to its Python twin by shared fixtures: the same
conventions, the same arithmetic in the same order, the same error
messages. What differs is only what the runtime forces — positions are
`Float32Array` because that is what a `BufferGeometry` wants, so the
JavaScript side carries a looser (single-precision) coordinate
tolerance than the float64 Python side. In practice the observed
departure is about one Float32 ulp. See {doc}`concepts`.

## Errors

- `SpecError` — not a valid molejo document, thrown by
  `parseSpec`/`validate`/`evaluate`, naming the element.
- `EvaluationError` — a valid document that cannot be evaluated at
  these values (or into these buffers), naming the parameter, slot or
  buffer.
- `NotImplementedError` (extends `EvaluationError`) — valid spec
  vocabulary this build does not evaluate: `loop: true` on a path that
  is not a `wrap`.
