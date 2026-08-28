// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// The shared invalid-document fixtures, run against the JS validator.
// The Python suite runs the same files and asserts the same substrings.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { parseSpec, SpecError } from '../src/index.js';

const FIXTURES = fileURLToPath(new URL('../../fixtures/invalid/', import.meta.url));

const files = readdirSync(FIXTURES).filter((name) => name.endsWith('.json')).sort();

test('the shared invalid-document fixtures exist', () => {
  assert.ok(files.length > 0, `no invalid-document fixtures found in ${FIXTURES}`);
});

for (const filename of files) {
  const fixture = JSON.parse(readFileSync(join(FIXTURES, filename), 'utf8'));

  test(`invalid fixture rejected naming the offending element: ${filename}`, () => {
    assert.ok(fixture.name, `${filename} has no name`);
    assert.ok(fixture.must_mention.length > 0, `${filename} asserts nothing about the message`);

    let caught;
    try {
      parseSpec(fixture.spec);
    } catch (error) {
      caught = error;
    }
    assert.ok(caught, `${filename}: parseSpec accepted an invalid document`);
    assert.ok(caught instanceof SpecError, `${filename}: threw ${caught} instead of a SpecError`);
    for (const substring of fixture.must_mention) {
      assert.ok(
        caught.message.includes(substring),
        `${filename}: error message ${JSON.stringify(caught.message)} does not mention ${JSON.stringify(substring)}`,
      );
    }
  });
}
