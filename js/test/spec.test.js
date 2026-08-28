// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// Structural validation of the canonical document, in the browser
// runtime. The JS package is evaluation-only: it parses and validates
// the document the Python authoring layer emits, and never authors one.

import test from 'node:test';
import assert from 'node:assert/strict';

import { parseSpec, parameterNames, evaluate, SpecError, SPEC_VERSION } from '../src/index.js';

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

test('the spec version is one', () => {
  assert.equal(SPEC_VERSION, 1);
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

test('evaluation is not implemented yet', () => {
  assert.throws(() => evaluate(spring(), { height: 46.8 }), /not implemented/);
});
