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

// --- the wrap, the polygon profile, and the closed loop -----------------
//
// The belt's geometry is pinned vertex for vertex by the three-pulley and
// carriage fixtures. What is asserted here is what a fixture cannot: the
// buffer counts a loop produces, the index that wraps its last ring onto
// its first, the reuse a running belt needs, and the refusals -- byte for
// byte the Python evaluator's.

const SECTION = [[-0.4, -3.0], [0.9, -3.0], [0.9, 3.0], [-0.4, 3.0]];

function belt({
  around = [
    { center: [0.0, 0.0], radius: 8.0 },
    { center: [30.0, 40.0], radius: 3.0 },
    { center: [60.0, 0.0], radius: 5.0 },
  ],
  teeth,
  anchor,
  phase,
  path = 8,
} = {}) {
  const wrap = { type: 'wrap', around };
  if (teeth !== undefined) wrap.teeth = teeth;
  if (anchor !== undefined) wrap.anchor = anchor;
  if (phase !== undefined) wrap.phase = phase;
  return {
    molejo: 1,
    profile: { type: 'polygon', points: SECTION },
    path: [wrap],
    loop: true,
    tessellation: { path, profile: SECTION.length },
  };
}

const TEETH = { pitch: 2.5, height: 0.75, flank: 'trapezoid', count: 6 };

test('a loop carries no cap centres and one more band of walls', () => {
  const buffers = evaluate(belt({ path: 8 }), {});
  // 2 elements a circle at 8 segments each: 48 rings, V = R*M, F = 2*R*M.
  assert.equal(buffers.vertexCount, 48 * 4);
  assert.equal(buffers.triangleCount, 2 * 48 * 4);
  assert.equal(buffers.positions.length, 48 * 4 * 3);
});

test("the last ring's quads wrap onto ring 0", () => {
  const buffers = evaluate(belt({ path: 8 }), {});
  const rings = 48;
  const at = 2 * (rings - 1) * 4 * 3;
  const last = (rings - 1) * 4;
  assert.deepEqual([...buffers.index.slice(at, at + 6)], [last, last + 1, 1, last, 1, 0]);
});

test('a closed belt is watertight', () => {
  assert.deepEqual(watertightFailures(evaluate(belt({ teeth: TEETH }), {}).index), []);
});

test('a toothed belt winds outward', () => {
  assert.ok(signedVolume(evaluate(belt({ teeth: TEETH }), {})) > 0.0);
});

test('neither a moving idler nor a phase touches the index', () => {
  const document = belt({
    around: [
      { center: [0.0, 0.0], radius: 8.0 },
      { center: [30.0, { param: 'idler' }], radius: 3.0 },
      { center: [60.0, 0.0], radius: 5.0 },
    ],
    teeth: TEETH,
    phase: { param: 'travel' },
  });
  const still = evaluate(document, { idler: 40.0, travel: 0.0 });
  const running = evaluate(document, { idler: 52.0, travel: 7.3 });
  assert.deepEqual([...still.index], [...running.index]);
  assert.notDeepEqual([...still.positions], [...running.positions]);
});

test('a running belt re-evaluates into the caller buffers', () => {
  const document = belt({ teeth: TEETH, phase: { param: 'travel' } });
  const buffers = evaluate(document, { travel: 0.0 });
  const before = [...buffers.positions];
  const again = evaluate(document, { travel: 3.1 }, buffers);
  assert.equal(again, buffers);
  assert.equal(again.positions, buffers.positions);
  assert.notDeepEqual([...buffers.positions], before);
});

test('a polygon profile is its declared points, in order', () => {
  const document = {
    molejo: 1,
    profile: { type: 'polygon', points: [[0, 0], [4, 0], [4, 1], [1, 3]] },
    path: [{ type: 'line', to: [0.0, 0.0, 10.0] }],
    loop: false,
    tessellation: { path: 2, profile: 4 },
  };
  const buffers = evaluate(document, {});
  assert.equal(buffers.vertexCount, 3 * 4 + 2);
  assert.deepEqual([...buffers.positions.slice(0, 12)], [0, 0, 0, 4, 0, 0, 4, 1, 0, 1, 3, 0]);
});

// The messages are the Python evaluator's, byte for byte.
const REFUSED = [
  [
    'a circle with no radius',
    belt({
      around: [
        { center: [0.0, 0.0], radius: 0.0 },
        { center: [0.0, 210.0], radius: 5.1 },
      ],
    }),
    'path[0].around[0].radius: must be a positive number, got 0',
  ],
  [
    'circles too close for an external tangent',
    belt({
      around: [
        { center: [0.0, 0.0], radius: 8.0 },
        { center: [0.0, 4.0], radius: 2.0 },
      ],
    }),
    'path[0].around[1]: a wrap needs an external tangent between consecutive ' +
      'circles; around[0] and around[1] are too close for one',
  ],
  [
    'a negative tooth height',
    belt({ teeth: { pitch: 2.5, height: -0.75, flank: 'trapezoid', count: 6 } }),
    'path[0].teeth.height: must be a non-negative number, got -0.75',
  ],
];

for (const [label, document, message] of REFUSED) {
  test(`${label} is refused, naming the slot`, () => {
    assert.throws(
      () => evaluate(document, {}),
      (error) => error instanceof EvaluationError && error.message === message,
    );
  });
}

test('a dangling parameter in a circle names its slot', () => {
  const document = belt({
    around: [
      { center: [0.0, 0.0], radius: 5.1 },
      { center: [{ param: 'x' }, 210.0], radius: 5.1 },
    ],
  });
  assert.throws(
    () => evaluate(document, {}),
    (error) =>
      /path\[0\]\.around\[1\]\.center\[0\]/.test(error.message) && /x/.test(error.message),
  );
});

// --- the spline and the loom --------------------------------------------
//
// The loom's geometry is pinned vertex for vertex by the filament-loom and
// loom-lead-in fixtures. What is asserted here is what a fixture cannot:
// the counts a spline of several spans produces, the ends it reaches, the
// reuse a running head needs, and the refusals -- byte for byte the Python
// evaluator's.

const ENTRY = [0.0, 1.0, 0.0];
const DOWN = [0.0, 0.0, -1.0];
const SAG = [[0.0, 90.0, -35.0], [60.0, 170.0, -10.0]];
const HEAD = [{ param: 'head_x' }, { param: 'head_y' }, { param: 'head_z' }];
const NEAR = { head_x: 95.0, head_y: 215.0, head_z: -45.0 };
const FAR = { head_x: 140.0, head_y: 190.0, head_z: -20.0 };

function loom({
  points = [...SAG, HEAD],
  startTangent = ENTRY,
  endTangent = DOWN,
  lead,
  path = 6,
  profile = 8,
} = {}) {
  const spline = { type: 'spline', points };
  if (startTangent !== undefined) spline.start_tangent = startTangent;
  if (endTangent !== undefined) spline.end_tangent = endTangent;
  return {
    molejo: 1,
    profile: { type: 'circle', radius: 2.0 },
    path: lead === undefined ? [spline] : [{ type: 'line', to: lead }, spline],
    loop: false,
    tessellation: { path, profile },
  };
}

test('a spline spends the declared segments on every span', () => {
  // Three declared points are three spans at 6 segments each: 19 rings.
  const buffers = evaluate(loom(), NEAR);
  assert.equal(buffers.vertexCount, 19 * 8 + 2);
  assert.equal(buffers.triangleCount, 2 * 18 * 8 + 2 * 8);
});

test('one declared point is one span', () => {
  assert.equal(evaluate(loom({ points: [HEAD] }), NEAR).vertexCount, 7 * 8 + 2);
});

test('a spline in a chain spends its segments per span', () => {
  // Five on the line -- its last ring is the joint, owned by the spline --
  // then three spans at five each: 21 rings.
  const buffers = evaluate(loom({ lead: [0.0, 20.0, 0.0], path: 5 }), NEAR);
  assert.equal(buffers.vertexCount, 21 * 8 + 2);
});

test('both ends are hit exactly', () => {
  // The Hermite basis is exactly (1, 0, 0, 0) at t = 0 and (0, 0, 1, 0) at
  // t = 1, so the two cap centres are the declared ends themselves --
  // exactly here too, because Float32 holds these numbers.
  const buffers = evaluate(loom(), NEAR);
  const at = 19 * 8 * 3;
  assert.deepEqual([...buffers.positions.slice(at, at + 3)], [0, 0, 0]);
  assert.deepEqual(
    [...buffers.positions.slice(at + 3, at + 6)],
    [NEAR.head_x, NEAR.head_y, NEAR.head_z],
  );
});

test('a loom is watertight and winds outward', () => {
  const buffers = evaluate(loom({ path: 9, profile: 16 }), NEAR);
  assert.deepEqual(watertightFailures(buffers.index), []);
  assert.ok(signedVolume(buffers) > 0.0);
});

test('a moving head touches no index', () => {
  const near = evaluate(loom(), NEAR);
  const far = evaluate(loom(), FAR);
  assert.deepEqual([...near.index], [...far.index]);
  assert.notDeepEqual([...near.positions], [...far.positions]);
});

test('a running head re-evaluates into the caller buffers', () => {
  const buffers = evaluate(loom(), NEAR);
  const before = [...buffers.positions];
  const again = evaluate(loom(), FAR, buffers);
  assert.equal(again, buffers);
  assert.equal(again.positions, buffers.positions);
  assert.notDeepEqual([...buffers.positions], before);
});

test('a declared tangent is a direction and its length is ignored', () => {
  const plain = evaluate(loom({ startTangent: [0.0, 1.0, 0.0] }), NEAR);
  const stretched = evaluate(loom({ startTangent: [0.0, 37.5, 0.0] }), NEAR);
  assert.deepEqual([...stretched.positions], [...plain.positions]);
});

test('without a start tangent a spline leaves the way it came', () => {
  // The lead-in runs along +Y, so the joint ring lies across it: every
  // vertex of that ring is at y = 20.
  const segments = 6;
  const buffers = evaluate(loom({ lead: [0.0, 20.0, 0.0], path: segments }), NEAR);
  for (let j = 0; j < 8; j += 1) {
    assert.ok(Math.abs(buffers.positions[(segments * 8 + j) * 3 + 1] - 20.0) < 1e-4);
  }
});

// The messages are the Python evaluator's, byte for byte.
const SPLINE_REFUSED = [
  [
    'a point coinciding with the one before it',
    loom({ points: [[0, 0, 0], [10, 0, 0]] }),
    'path[0].points[0]: a spline must go somewhere; points[0] coincides with ' +
      'the point before it',
  ],
  [
    'a start tangent with no direction',
    loom({ startTangent: [0.0, 0.0, 0.0] }),
    "path[0].start_tangent: a spline's start tangent needs a direction; it has " +
      'no length',
  ],
  [
    'an end tangent with no direction',
    loom({ endTangent: [0.0, 0.0, 0.0] }),
    "path[0].end_tangent: a spline's end tangent needs a direction; it has no length",
  ],
  [
    'a point whose neighbours coincide',
    loom({
      points: [[0, 40, 0], [0, 0, 0], [0, 60, 0]],
      startTangent: [0, 1, 0],
      endTangent: [0, 1, 0],
    }),
    'path[0].points[0]: a spline needs a direction where it turns; the points ' +
      'on either side of points[0] coincide',
  ],
];

for (const [label, document, message] of SPLINE_REFUSED) {
  test(`${label} is refused, naming the slot`, () => {
    assert.throws(
      () => evaluate(document, NEAR),
      (error) => error instanceof EvaluationError && error.message === message,
    );
  });
}

test('a dangling parameter in a spline point names its slot', () => {
  assert.throws(
    () => evaluate(loom(), { head_x: 95.0, head_y: 215.0 }),
    (error) =>
      /path\[0\]\.points\[2\]\[2\]/.test(error.message) && /head_z/.test(error.message),
  );
});

test('a dangling parameter in a tangent names its slot', () => {
  assert.throws(
    () => evaluate(loom({ endTangent: [0.0, 0.0, { param: 'aim' }] }), NEAR),
    (error) =>
      /path\[0\]\.end_tangent\[2\]/.test(error.message) && /aim/.test(error.message),
  );
});

// --- what this batch does not evaluate yet ------------------------------

test('a closed loop that is not a wrap is not evaluated yet', () => {
  const document = cylinder();
  document.loop = true;
  assert.throws(
    () => evaluate(document, {}),
    (error) =>
      error.message ===
      'loop: closing a chain of primitives is not implemented yet; this molejo ' +
        "build closes the loop of a 'wrap' path only",
  );
});

test('a degenerate spline in a chain names its own position', () => {
  const document = loom({ points: [[0, 0, 20], [10, 0, 20]], lead: [0, 0, 20] });
  assert.throws(() => evaluate(document, {}), /path\[1\]\.points\[0\]/);
});
