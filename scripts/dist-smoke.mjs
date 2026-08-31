// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0
//
// What an installed molejo npm package must do, run from outside the
// repository.
//
// `scripts/check-dist-js` copies this file into a throwaway scratch project
// that has installed the packed tarball, and runs it there. Nothing here can
// reach the source tree: a bare `molejo` specifier that resolves is the
// installed package, not the checkout. The fixture arrives as an argument
// for the same reason -- the parity fixtures are repository data, deliberately
// not shipped in the tarball.
//
// Usage: node dist-smoke.mjs <cylinder-fixture.json>

import { readFileSync } from 'node:fs';

import {
  SPEC_VERSION,
  SPEC_VERSIONS,
  VERSION,
  evaluate,
  parameterNames,
  parseSpec,
} from 'molejo';

function check(condition, message) {
  if (!condition) {
    console.error(`dist-smoke: ${message}`);
    process.exit(1);
  }
}

function report(line) {
  console.log(`  ${line}`);
}

// --- the installed package, not the checkout -------------------------------

const resolved = import.meta.resolve('molejo');
check(
  resolved.includes('/node_modules/molejo/'),
  `resolved molejo to ${resolved}, which is not an installed package`,
);
report(
  `molejo ${VERSION} (reads spec ${SPEC_VERSIONS.join(', ')}, writes at most ` +
    `${SPEC_VERSION}) resolved from ${resolved}`,
);

// --- the cylinder parity fixture, from the repository ----------------------

const [fixturePath] = process.argv.slice(2);
check(fixturePath !== undefined, 'usage: node dist-smoke.mjs <cylinder-fixture.json>');
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8'));
const tolerance = fixture.tolerance.js;

const document = parseSpec(fixture.spec);
// A version this implementation reads, not the newest it reads: the
// cylinder is a spec 0.1 document and must stay one.
check(
  SPEC_VERSIONS.includes(document.molejo),
  `the fixture declares spec version ${document.molejo}, which this build does not read`,
);
const names = [...parameterNames(fixture.spec)].sort();
check(
  names.length === 1 && names[0] === 'length',
  `the cylinder's parameters are ${JSON.stringify(names)}`,
);
report(`cylinder spec parsed: parameters ${JSON.stringify(names)}`);

function compare(where, buffers, expectedVertices) {
  check(
    buffers.positions.length === expectedVertices.length * 3,
    `${where}: ${buffers.positions.length / 3} vertices, expected ${expectedVertices.length}`,
  );
  check(
    buffers.index.length === fixture.faces.length * 3,
    `${where}: ${buffers.index.length / 3} faces, expected ${fixture.faces.length}`,
  );

  for (let face = 0; face < fixture.faces.length; face += 1) {
    for (let corner = 0; corner < 3; corner += 1) {
      const actual = buffers.index[face * 3 + corner];
      const wanted = fixture.faces[face][corner];
      check(
        actual === wanted,
        `${where}: face ${face} corner ${corner} is ${actual}, expected ${wanted}`,
      );
    }
  }

  let worst = 0;
  for (let vertex = 0; vertex < expectedVertices.length; vertex += 1) {
    for (let axis = 0; axis < 3; axis += 1) {
      const actual = buffers.positions[vertex * 3 + axis];
      const wanted = expectedVertices[vertex][axis];
      const margin = Math.abs(actual - wanted) / (1 + Math.abs(wanted));
      worst = Math.max(worst, margin);
      check(
        margin <= tolerance,
        `${where}: vertex ${vertex} axis ${axis} is ${actual}, expected ${wanted} ` +
          `(margin ${margin} > ${tolerance})`,
      );
    }
  }
  return worst;
}

let worst = 0;
for (const testCase of fixture.cases) {
  const buffers = evaluate(fixture.spec, testCase.values);
  worst = Math.max(worst, compare(testCase.name, buffers, testCase.vertices));
}
report(
  `cylinder fixture matched over ${fixture.cases.length} cases: ` +
    `worst margin ${worst.toExponential(3)}, tolerance ${tolerance}`,
);

// --- buffer reuse ----------------------------------------------------------
//
// The point of fixed tessellation: the same shape at new parameter values
// writes into the buffers a consumer already handed to three.js. Same object,
// same typed arrays, same index -- only the positions move.

const [first, ...rest] = fixture.cases;
const buffers = evaluate(fixture.spec, first.values);
const positions = buffers.positions;
const index = buffers.index;
const indexBefore = Uint32Array.from(index);

for (const testCase of rest) {
  const again = evaluate(fixture.spec, testCase.values, buffers);
  check(again === buffers, 'reuse returned a different buffers object');
  check(again.positions === positions, 'reuse replaced the positions array');
  check(again.index === index, 'reuse replaced the index array');
  check(
    indexBefore.every((value, at) => value === index[at]),
    'reuse rewrote the index of a shape whose tessellation did not change',
  );
  compare(`${testCase.name} (reused)`, again, testCase.vertices);
}

check(rest.length > 0, 'the fixture has only one case, so reuse was never exercised');
report(
  `buffers reused across ${fixture.cases.length} cases: ` +
    `${positions.length / 3} vertices rewritten in place, index untouched`,
);

console.log('dist-smoke: the installed package parses, evaluates and reuses buffers.');
