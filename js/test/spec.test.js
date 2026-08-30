// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// Structural validation of the canonical document, in the browser
// runtime. The JS package is evaluation-only: it parses and validates
// the document the Python authoring layer emits, and never authors one.

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  parseSpec,
  parameterNames,
  evaluate,
  requiredVersion,
  SpecError,
  SPEC_VERSION,
  SPEC_VERSIONS,
} from '../src/index.js';

const SPRING_DOCUMENT = {
  molejo: 1,
  profile: { type: 'circle', radius: 2.0 },
  path: [{ type: 'helix', radius: 14.0, turns: 6.5, height: { param: 'height' } }],
  loop: false,
  tessellation: { path: 240, profile: 16 },
};

function spring() {
  return JSON.parse(JSON.stringify(SPRING_DOCUMENT));
}

test('the spec versions read are one and two', () => {
  // Two, because v2 only adds vocabulary: every v1 document still says
  // what it always said. SPEC_VERSION is the newest of them.
  assert.deepEqual(SPEC_VERSIONS, [1, 2]);
  assert.equal(SPEC_VERSION, 2);
});

test('a document declares the lowest version it needs', () => {
  assert.equal(requiredVersion(spring()), 1);
});

test('a v1 document may not use v2 vocabulary', () => {
  const document = {
    molejo: 1,
    profile: {
      type: 'polygon',
      points: [[-0.4, -1.0], [0.9, -1.0], [0.9, 1.0], [-0.4, 1.0]],
    },
    path: [{
      type: 'wrap',
      around: [
        { center: [0.0, 0.0], radius: 8.0 },
        { center: [30.0, 4.0], radius: 3.0, turn: 'counterclockwise' },
        { center: [60.0, 0.0], radius: 8.0 },
      ],
    }],
    loop: true,
    tessellation: { path: 12, profile: 4 },
  };
  assert.equal(requiredVersion(document), 2);
  assert.throws(() => parseSpec(document), (error) =>
    error instanceof SpecError && error.message.includes('path[0].around[1].turn'));

  document.molejo = 2;
  assert.deepEqual(parseSpec(document), document);
});

test('the canonical spring document parses', () => {
  assert.deepEqual(parseSpec(spring()), SPRING_DOCUMENT);
});

test('a JSON string parses', () => {
  assert.deepEqual(parseSpec(JSON.stringify(SPRING_DOCUMENT)), SPRING_DOCUMENT);
});

test('text that is not JSON is rejected', () => {
  assert.throws(() => parseSpec('{not json'), SpecError);
});

test('loop is optional and defaults to false', () => {
  const document = spring();
  delete document.loop;
  assert.equal(parseSpec(document).loop, false);
});

test('parsing does not mutate the caller document', () => {
  const document = spring();
  delete document.loop;
  parseSpec(document);
  assert.equal('loop' in document, false);
});

test('every v1 path primitive parses', () => {
  const primitives = [
    { type: 'line', to: [0.0, 0.0, 10.0] },
    { type: 'line', to: [{ param: 'x' }, 0.0, { param: 'z' }] },
    { type: 'arc', center: [0, 0, 0], axis: [0, 0, 1], angle: { param: 'sweep' } },
    { type: 'helix', radius: 14.0, turns: 6.5, height: 46.8 },
    { type: 'spline', points: [[0, 0, 0], [1, 2, 3]] },
    { type: 'spline', points: [[{ param: 'x' }, 2, 3]] },
    {
      type: 'spline',
      points: [[0.0, 90.0, -35.0], [{ param: 'x' }, 2, 3]],
      start_tangent: [0.0, 1.0, 0.0],
      end_tangent: [0.0, 0.0, { param: 'aim' }],
    },
    {
      type: 'wrap',
      around: [
        { center: [0, 0], radius: 5.1 },
        { center: [0, 210], radius: 5.1 },
      ],
      teeth: { pitch: 2.5, height: 0.7, flank: 'trapezoid', count: 180 },
      anchor: { span: 0, at: { param: 'y' } },
    },
    {
      type: 'wrap',
      around: [
        { center: [0, 0], radius: 5.1 },
        { center: [0, 210], radius: 5.1 },
      ],
      phase: { param: 'travel' },
    },
  ];
  for (const primitive of primitives) {
    const document = spring();
    document.path = [primitive];
    // A wrap is a closed loop and the only primitive of its path, so it
    // can only be parsed in a document that says so.
    if (primitive.type === 'wrap') document.loop = true;
    assert.deepEqual(parseSpec(document).path, [primitive]);
  }
});

test('every v1 profile parses', () => {
  const profiles = [
    { type: 'circle', radius: 2.0 },
    { type: 'circle', radius: { param: 'wire' } },
    { type: 'polygon', points: [[-1, 0], [1, 0], [0, 1.5]] },
  ];
  for (const profile of profiles) {
    const document = spring();
    document.profile = profile;
    // A polygon is sampled at its own points, no more and no fewer.
    if (profile.type === 'polygon') document.tessellation.profile = profile.points.length;
    assert.deepEqual(parseSpec(document).profile, profile);
  }
});

test('a document that is not an object is rejected', () => {
  assert.throws(() => parseSpec([1, 2, 3]), /spec/);
  assert.throws(() => parseSpec(null), /spec/);
});

test('a dangling parameter is not a structural error', () => {
  const parsed = parseSpec(spring());
  assert.deepEqual([...parameterNames(parsed)].sort(), ['height']);
});

test('parameter names are collected from profile and path', () => {
  const document = spring();
  document.profile = { type: 'circle', radius: { param: 'wire' } };
  document.path = [
    { type: 'line', to: [{ param: 'x' }, { param: 'y' }, 0.0] },
    { type: 'arc', center: [0, 0, 0], axis: [0, 0, 1], angle: { param: 'x' } },
  ];
  assert.deepEqual([...parameterNames(parseSpec(document))].sort(), ['wire', 'x', 'y']);
});

test('a boolean is not a number', () => {
  const document = spring();
  document.profile.radius = true;
  assert.throws(() => parseSpec(document), /profile\.radius/);
});

test('a non-finite number is rejected', () => {
  const document = spring();
  document.profile.radius = Infinity;
  assert.throws(() => parseSpec(document), /profile\.radius/);
});

test('an empty parameter name is rejected', () => {
  const document = spring();
  document.profile.radius = { param: '' };
  assert.throws(() => parseSpec(document), /profile\.radius/);
});

test('a spec error is an error', () => {
  assert.ok(SpecError.prototype instanceof Error);
});

test('every v1 path primitive evaluates', () => {
  // The whole path vocabulary is implemented, so there is no branch left
  // that names one as missing: an unknown type is a structural refusal.
  const document = spring();
  document.path = [
    {
      type: 'spline',
      points: [[0.0, 90.0, -35.0], [95.0, 215.0, -45.0]],
      start_tangent: [0.0, 1.0, 0.0],
      end_tangent: [0.0, 0.0, -1.0],
    },
  ];
  assert.equal(evaluate(document, { height: 46.8 }).vertexCount, 481 * 16 + 2);
});

test('the canonical spring document evaluates', () => {
  // The shape the README advertises, at the resolution it declares.
  assert.equal(evaluate(spring(), { height: 46.8 }).vertexCount, 241 * 16 + 2);
});
