// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// The browser-side evaluation of the cylinder slice.
//
// The shared parity fixtures (see ./parity-fixtures.test.js) are what
// hold this evaluator to the Python one vertex for vertex. What is
// asserted here is everything the fixtures cannot: the shape of the
// buffers three.js wants, the in-place re-evaluation a viewer needs to
// run per frame without allocating, and the failure contract -- throw
// naming the offending element, write nothing.

import test from 'node:test';
import assert from 'node:assert/strict';

import { evaluate, EvaluationError, SpecError } from '../src/index.js';

function cylinder({ radius = 5.0, to = [0.0, 0.0, 12.0], path = 4, profile = 12 } = {}) {
  return {
    molejo: 1,
    profile: { type: 'circle', radius },
    path: [{ type: 'line', to }],
    loop: false,
    tessellation: { path, profile },
  };
}

// --- independent mesh arithmetic ---------------------------------------

function signedVolume(buffers) {
  const { positions, index } = buffers;
  let total = 0.0;
  for (let t = 0; t < index.length; t += 3) {
    const [a, b, c] = [index[t] * 3, index[t + 1] * 3, index[t + 2] * 3];
    const [ax, ay, az] = [positions[a], positions[a + 1], positions[a + 2]];
    const [bx, by, bz] = [positions[b], positions[b + 1], positions[b + 2]];
    const [cx, cy, cz] = [positions[c], positions[c + 1], positions[c + 2]];
    total +=
      ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx);
  }
  return total / 6.0;
}

function watertightFailures(index) {
  const counts = new Map();
  const bump = (a, b) => counts.set(`${a},${b}`, (counts.get(`${a},${b}`) ?? 0) + 1);
  for (let t = 0; t < index.length; t += 3) {
    bump(index[t], index[t + 1]);
    bump(index[t + 1], index[t + 2]);
    bump(index[t + 2], index[t]);
  }
  const failures = [];
  for (const [edge, count] of counts) {
    const [a, b] = edge.split(',');
    if (count !== 1) failures.push(`directed edge ${edge} used ${count} times`);
    if ((counts.get(`${b},${a}`) ?? 0) !== 1) failures.push(`edge ${edge} is unmatched`);
  }
  return failures;
}

function prismVolume(radius, length, profile) {
  return 0.5 * profile * radius * radius * Math.sin((2 * Math.PI) / profile) * length;
}

// --- the buffers three.js wants ----------------------------------------

test('evaluation returns Float32 positions and a Uint32 index', () => {
  const buffers = evaluate(cylinder(), {});
  assert.ok(buffers.positions instanceof Float32Array);
  assert.ok(buffers.index instanceof Uint32Array);
});

test('the buffers carry the counts the tessellation declares', () => {
  const buffers = evaluate(cylinder({ path: 4, profile: 12 }), {});
  const vertices = 5 * 12 + 2;
  const triangles = 2 * 4 * 12 + 2 * 12;
  assert.equal(buffers.positions.length, vertices * 3);
  assert.equal(buffers.index.length, triangles * 3);
  assert.equal(buffers.vertexCount, vertices);
  assert.equal(buffers.triangleCount, triangles);
});

test('a JSON string is as good an input as a parsed document', () => {
  const document = cylinder();
  const fromText = evaluate(JSON.stringify(document), {});
  const fromObject = evaluate(document, {});
  assert.deepEqual([...fromText.positions], [...fromObject.positions]);
});

test('evaluation does not mutate the caller document', () => {
  const document = cylinder();
  const before = JSON.stringify(document);
  evaluate(document, {});
  assert.equal(JSON.stringify(document), before);
});

test('the cylinder is watertight', () => {
  assert.deepEqual(watertightFailures(evaluate(cylinder(), {}).index), []);
});

test('the cylinder encloses the volume the tessellation describes', () => {
  const buffers = evaluate(cylinder({ radius: 5.0, path: 4, profile: 12 }), {});
  const expected = prismVolume(5.0, 12.0, 12);
  assert.ok(
    Math.abs(signedVolume(buffers) - expected) < 1e-4 * expected,
    `volume ${signedVolume(buffers)} is not ${expected}`,
  );
});

test('every triangle winds outward', () => {
  const { positions, index } = evaluate(cylinder(), {});
  const centre = [0.0, 0.0, 6.0];
  for (let t = 0; t < index.length; t += 3) {
    const corners = [0, 1, 2].map((k) => {
      const base = index[t + k] * 3;
      return [positions[base], positions[base + 1], positions[base + 2]];
    });
    const u = corners[1].map((v, axis) => v - corners[0][axis]);
    const v = corners[2].map((w, axis) => w - corners[0][axis]);
    const normal = [
      u[1] * v[2] - u[2] * v[1],
      u[2] * v[0] - u[0] * v[2],
      u[0] * v[1] - u[1] * v[0],
    ];
    const middle = [0, 1, 2].map(
      (axis) => (corners[0][axis] + corners[1][axis] + corners[2][axis]) / 3.0 - centre[axis],
    );
    const dot = normal.reduce((sum, n, axis) => sum + n * middle[axis], 0.0);
    assert.ok(dot > 0.0, `triangle ${t / 3} faces inward`);
  }
});

// --- parameters ---------------------------------------------------------

test('a parameter moves the vertices and renumbers nothing', () => {
  const document = cylinder({ to: [0.0, 0.0, { param: 'length' }] });
  const short = evaluate(document, { length: 5.0 });
  const tall = evaluate(document, { length: 50.0 });
  assert.deepEqual([...short.index], [...tall.index]);
  assert.notDeepEqual([...short.positions], [...tall.positions]);
});

test('repeated evaluation under one binding is identical', () => {
  const document = cylinder({ to: [0.0, 0.0, { param: 'length' }] });
  const first = evaluate(document, { length: 17.5 });
  const second = evaluate(document, { length: 17.5 });
  assert.deepEqual([...first.positions], [...second.positions]);
});

test('values the spec does not reference are ignored', () => {
  const document = cylinder({ to: [0.0, 0.0, { param: 'length' }] });
  const plain = evaluate(document, { length: 9.0 });
  const noisy = evaluate(document, { length: 9.0, motorAngle: 1.7 });
  assert.deepEqual([...plain.positions], [...noisy.positions]);
});

// --- per-frame affordability --------------------------------------------

test('re-evaluation fills the caller buffers in place and allocates nothing', () => {
  const document = cylinder({ to: [0.0, 0.0, { param: 'length' }] });
  const buffers = evaluate(document, { length: 12.0 });
  const positions = buffers.positions;
  const index = buffers.index;

  const again = evaluate(document, { length: 30.0 }, buffers);
  assert.equal(again, buffers, 'the same object comes back');
  assert.equal(again.positions, positions, 'the positions array was reused');
  assert.equal(again.index, index, 'the index array was reused');
  assert.notDeepEqual([...positions], [...evaluate(document, { length: 12.0 }).positions]);
});

test('the index does not change for a given spec', () => {
  const document = cylinder({ to: [0.0, 0.0, { param: 'length' }] });
  const buffers = evaluate(document, { length: 12.0 });
  const before = [...buffers.index];
  evaluate(document, { length: 30.0 }, buffers);
  assert.deepEqual([...buffers.index], before);
});

test('buffers from another spec are refused rather than half-filled', () => {
  const buffers = evaluate(cylinder({ profile: 12 }), {});
  assert.throws(
    () => evaluate(cylinder({ profile: 16 }), {}, buffers),
    (error) => error instanceof EvaluationError && /positions/.test(error.message),
  );
});

// --- loud failure, no partial output ------------------------------------

test('a dangling parameter throws naming it and the slot', () => {
  assert.throws(
    () => evaluate(cylinder({ to: [0.0, 0.0, { param: 'length' }] }), {}),
    (error) =>
      error instanceof EvaluationError &&
      error.message.includes('length') &&
      error.message.includes('path[0].to[2]'),
  );
});

test('a dangling parameter writes nothing into the caller buffers', () => {
  const document = cylinder({ to: [0.0, 0.0, { param: 'length' }] });
  const buffers = evaluate(document, { length: 12.0 });
  const before = [...buffers.positions];
  assert.throws(() => evaluate(document, {}, buffers), EvaluationError);
  assert.deepEqual([...buffers.positions], before, 'a failed frame left debris');
});

test('a non-numeric value throws naming the parameter', () => {
  assert.throws(
    () => evaluate(cylinder({ to: [0.0, 0.0, { param: 'lift' }] }), { lift: 'high' }),
    (error) => /lift/.test(error.message) && /a string/.test(error.message),
  );
});

for (const [label, value] of [
  ['NaN', NaN],
  ['Infinity', Infinity],
  ['null', null],
  ['a boolean', true],
]) {
  test(`a ${label} parameter value throws`, () => {
    assert.throws(
      () => evaluate(cylinder({ to: [0.0, 0.0, { param: 'lift' }] }), { lift: value }),
      EvaluationError,
    );
  });
}

test('an invalid document is rejected before any geometry', () => {
  const document = cylinder();
  document.path = [{ type: 'squiggle' }];
  assert.throws(() => evaluate(document, {}), SpecError);
});

test('a line with no direction is refused', () => {
  assert.throws(
    () => evaluate(cylinder({ to: [0.0, 0.0, 0.0] }), {}),
    (error) => /path\[0\]\.to/.test(error.message),
  );
});

test('a non-positive radius is refused', () => {
  assert.throws(
    () => evaluate(cylinder({ radius: { param: 'wire' } }), { wire: 0.0 }),
    (error) => /profile\.radius/.test(error.message),
  );
});

// --- chained paths, arcs, and helices -----------------------------------
//
// The geometry of a chain is pinned vertex for vertex by the quarter-bend
// and spring fixtures. What is asserted here is what a fixture cannot
// say: the buffer counts a chain produces, that they survive a parameter,
// and that every degenerate primitive throws the message its Python twin
// throws, to the byte.

function bend({ reach = 20.0, path = 4, profile = 8 } = {}) {
  return {
    molejo: 1,
    profile: { type: 'circle', radius: 1.5 },
    path: [
      { type: 'line', to: [0.0, 0.0, 10.0] },
      {
        type: 'arc',
        center: [6.0, 0.0, 10.0],
        axis: [0.0, 1.0, 0.0],
        angle: Math.PI / 2.0,
      },
      { type: 'line', to: [reach, 0.0, 16.0] },
    ],
    loop: false,
    tessellation: { path, profile },
  };
}

function spring({ turns = 2.5, height = 30.0, path = 24, profile = 8 } = {}) {
  return {
    molejo: 1,
    profile: { type: 'circle', radius: 1.0 },
    path: [{ type: 'helix', radius: 6.0, turns, height }],
    loop: false,
    tessellation: { path, profile },
  };
}

test('a chain spends the declared segments on every primitive', () => {
  const buffers = evaluate(bend({ path: 4, profile: 8 }), {});
  // Three primitives at 4 segments each: 12 segments, 13 rings.
  assert.equal(buffers.vertexCount, 13 * 8 + 2);
  assert.equal(buffers.triangleCount, 2 * 12 * 8 + 2 * 8);
});

test('a chained sweep is watertight', () => {
  assert.deepEqual(watertightFailures(evaluate(bend(), {}).index), []);
  assert.deepEqual(watertightFailures(evaluate(spring(), {}).index), []);
});

test('a chain re-evaluates into the caller buffers', () => {
  const document = bend({ reach: { param: 'reach' } });
  const buffers = evaluate(document, { reach: 20.0 });
  const before = [...buffers.positions];
  const again = evaluate(document, { reach: 40.0 }, buffers);
  assert.equal(again, buffers);
  assert.notDeepEqual([...buffers.positions], before);
});

test('the coil count does not follow the pitch', () => {
  const document = spring({ height: { param: 'height' } });
  const free = evaluate(document, { height: 30.0 });
  const compressed = evaluate(document, { height: 12.0 });
  assert.deepEqual([...free.index], [...compressed.index]);
  assert.notDeepEqual([...free.positions], [...compressed.positions]);
});

// The messages are the Python evaluator's, byte for byte: a consumer that
// reads one runtime's diagnostics must not have to relearn the other's.
const DEGENERATE = [
  [
    'an arc with no axis',
    { type: 'arc', center: [6, 0, 0], axis: [0, 0, 0], angle: 1.0 },
    'path[0].axis: an arc needs an axis to turn about; its axis has no direction',
  ],
  [
    'an arc whose start lies on its axis',
    { type: 'arc', center: [0, 0, 0], axis: [0, 1, 0], angle: 1.0 },
    'path[0].center: an arc needs a radius to turn on; its start point lies on its axis',
  ],
  [
    'an arc that turns nowhere',
    { type: 'arc', center: [6, 0, 0], axis: [0, 1, 0], angle: 0.0 },
    'path[0].angle: an arc must turn somewhere; its angle is 0',
  ],
  [
    'a helix with no radius',
    { type: 'helix', radius: 0.0, turns: 2.5, height: 30.0 },
    'path[0].radius: must be a positive number, got 0',
  ],
  [
    'a helix that goes nowhere',
    { type: 'helix', radius: 6.0, turns: 0.0, height: 0.0 },
    'path[0]: a helix must go somewhere; it makes 0 turns and rises 0',
  ],
];

for (const [label, primitive, message] of DEGENERATE) {
  test(`${label} is refused, naming the slot`, () => {
    const document = cylinder();
    document.path = [primitive];
    assert.throws(
      () => evaluate(document, {}),
      (error) => error instanceof EvaluationError && error.message === message,
    );
  });
}

test('a degenerate primitive names its own position in the chain', () => {
  const document = bend();
  document.path[1].angle = 0.0;
  assert.throws(() => evaluate(document, {}), /path\[1\]\.angle/);
});

test('a dangling parameter in a later primitive names that slot', () => {
  assert.throws(
    () => evaluate(bend({ reach: { param: 'reach' } }), {}),
    (error) => /path\[2\]\.to\[0\]/.test(error.message) && /reach/.test(error.message),
  );
});

// --- what this batch does not evaluate yet ------------------------------

const UNIMPLEMENTED = [
  ['spline', { type: 'spline', points: [[0, 0, 0], [1, 2, 3]] }],
  [
    'wrap',
    {
      type: 'wrap',
      around: [
        { center: [0, 0], radius: 5.1 },
        { center: [0, 210], radius: 5.1 },
      ],
    },
  ],
];

for (const [name, primitive] of UNIMPLEMENTED) {
  test(`the '${name}' primitive names itself as unimplemented`, () => {
    const document = cylinder();
    document.path = [primitive];
    assert.throws(
      () => evaluate(document, {}),
      (error) =>
        error.message.includes(name) &&
        error.message.includes('path[0]') &&
        error.message.includes('not implemented'),
    );
  });
}

test('the polygon profile names itself as unimplemented', () => {
  const document = cylinder();
  document.profile = { type: 'polygon', points: [[0, 0], [1, 0], [0, 1]] };
  assert.throws(
    () => evaluate(document, {}),
    (error) => /polygon/.test(error.message) && /not implemented/.test(error.message),
  );
});

test('a closed loop is not evaluated yet', () => {
  const document = cylinder();
  document.loop = true;
  assert.throws(() => evaluate(document, {}), /loop/);
});

test('an unimplemented primitive names its position in a chain', () => {
  const document = bend();
  document.path[2] = { type: 'spline', points: [[0, 0, 0], [1, 2, 3]] };
  assert.throws(
    () => evaluate(document, {}),
    (error) =>
      error.message ===
      "path[2]: the 'spline' path primitive is not implemented yet; this molejo " +
        "build evaluates 'line', 'arc' and 'helix' only",
  );
});
