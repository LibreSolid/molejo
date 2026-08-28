// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// The shared parity fixtures, run against the JS evaluator.
//
// `python/tests/test_parity_fixtures.py` is this file's twin: same
// fixtures, same discovery, same comparison, a tolerance chosen for its
// own runtime. Neither side keeps a list of fixtures of its own -- both
// read `fixtures/manifest.json` and both assert it agrees with the
// directory -- so a fixture added for one runtime cannot be silently
// skipped by the other.
//
// Counts and ordering are exact; coordinates match within the fixture's
// declared tolerance, |actual - expected| <= tolerance * (1 + |expected|).
// Single precision is why the JS tolerance is the looser of the two: a
// Float32 position cannot hold what float64 computed.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { evaluate, parameterNames } from '../src/index.js';

const FIXTURES = fileURLToPath(new URL('../../fixtures/', import.meta.url));
const MANIFEST = 'manifest.json';

const files = readdirSync(FIXTURES)
  .filter((name) => name.endsWith('.json') && name !== MANIFEST)
  .sort();

function load(filename) {
  return JSON.parse(readFileSync(join(FIXTURES, filename), 'utf8'));
}

const manifest = load(MANIFEST).parity;

// --- the comparison ----------------------------------------------------

/** Throw unless the buffers match the expectation, naming the first departure. */
export function compare(where, expectedVertices, expectedFaces, buffers, tolerance) {
  if (buffers.positions.length !== expectedVertices.length * 3) {
    throw new Error(
      `${where}: expected ${expectedVertices.length} vertices, ` +
        `got ${buffers.positions.length / 3}`,
    );
  }
  if (buffers.index.length !== expectedFaces.length * 3) {
    throw new Error(
      `${where}: expected ${expectedFaces.length} faces, got ${buffers.index.length / 3}`,
    );
  }

  for (let face = 0; face < expectedFaces.length; face += 1) {
    for (let corner = 0; corner < 3; corner += 1) {
      const actual = buffers.index[face * 3 + corner];
      const expected = expectedFaces[face][corner];
      if (actual !== expected) {
        throw new Error(
          `${where}: face ${face} corner ${corner} is ${actual}, expected ${expected}`,
        );
      }
    }
  }

  for (let vertex = 0; vertex < expectedVertices.length; vertex += 1) {
    for (let axis = 0; axis < 3; axis += 1) {
      const actual = buffers.positions[vertex * 3 + axis];
      const expected = expectedVertices[vertex][axis];
      const bound = tolerance * (1.0 + Math.abs(expected));
      const off = Math.abs(actual - expected);
      if (!(off <= bound)) {
        throw new Error(
          `${where}: vertex ${vertex} axis ${axis} is ${actual}, expected ${expected} ` +
            `(off by ${off.toExponential(3)}, tolerance ${bound.toExponential(3)})`,
        );
      }
    }
  }
}

/** Every case of one fixture, compared. Throws on the first departure. */
export function runFixture(filename, fixture) {
  const tolerance = fixture.tolerance.js;
  for (const testCase of fixture.cases) {
    const buffers = evaluate(fixture.spec, testCase.values);
    compare(
      `${filename} [${testCase.name}]`,
      testCase.vertices,
      fixture.faces,
      buffers,
      tolerance,
    );
  }
}

// --- both suites run every fixture -------------------------------------

test('there is at least one parity fixture', () => {
  assert.ok(files.length > 0, 'no parity fixtures found; the evaluators are pinned to nothing');
});

test('the manifest and the directory agree', () => {
  assert.deepEqual([...manifest].sort(), files);
});

for (const filename of files) {
  const fixture = load(filename);

  test(`a parity fixture matches the JS evaluation: ${filename}`, () => {
    runFixture(filename, fixture);
  });

  test(`a fixture binds exactly the parameters its spec references: ${filename}`, () => {
    const referenced = [...parameterNames(fixture.spec)].sort();
    for (const testCase of fixture.cases) {
      assert.deepEqual(Object.keys(testCase.values).sort(), referenced, testCase.name);
    }
  });

  test(`a fixture declares a tolerance for both runtimes: ${filename}`, () => {
    assert.deepEqual(Object.keys(fixture.tolerance).sort(), ['js', 'python']);
    assert.ok(fixture.tolerance.js > 0 && fixture.tolerance.python > 0);
    assert.ok(fixture.tolerance.js >= fixture.tolerance.python);
  });

  test(`a fixture carries more than one binding: ${filename}`, () => {
    assert.ok(fixture.cases.length >= 2);
  });

  // --- the comparison is held to account -------------------------------

  test(`a perturbed vertex fails the comparison: ${filename}`, () => {
    const perturbed = load(filename);
    perturbed.cases[0].vertices[7][1] += 1.0 + 1000.0 * perturbed.tolerance.js;
    assert.throws(() => runFixture(filename, perturbed), /vertex 7 axis 1/);
  });

  test(`a perturbed face fails the comparison: ${filename}`, () => {
    const perturbed = load(filename);
    perturbed.faces[3][2] = 0;
    assert.throws(() => runFixture(filename, perturbed), /face 3 corner 2/);
  });

  test(`a dropped vertex fails the comparison: ${filename}`, () => {
    const perturbed = load(filename);
    perturbed.cases[0].vertices.pop();
    assert.throws(() => runFixture(filename, perturbed), /vertices/);
  });

  test(`a dropped face fails the comparison: ${filename}`, () => {
    const perturbed = load(filename);
    perturbed.faces.pop();
    assert.throws(() => runFixture(filename, perturbed), /faces/);
  });

  test(`a perturbation inside tolerance still passes: ${filename}`, () => {
    // The other half of the proof: a comparator that fails everything is
    // no better than one that passes everything.
    const perturbed = load(filename);
    const inside = perturbed.tolerance.js / 2.0;
    for (const testCase of perturbed.cases) {
      for (const vertex of testCase.vertices) vertex[0] += inside;
    }
    runFixture(filename, perturbed);
  });
}
