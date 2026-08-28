// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// The browser-side evaluator's surface, ahead of its arithmetic: the
// tests in `js/test/evaluate.test.js` and the shared parity fixtures
// describe the cylinder slice this module owes them, and every one of
// them is red against this file.

/** A spec cannot be evaluated at the given parameter values. */
export class EvaluationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'EvaluationError';
  }
}

/** A valid part of the v1 vocabulary this build does not evaluate yet. */
export class NotImplementedError extends EvaluationError {
  constructor(message) {
    super(message);
    this.name = 'NotImplementedError';
  }
}

/**
 * Evaluate a spec at the given parameter values into vertex buffers.
 *
 * @param {string|object} spec
 * @param {object} values named scalar parameters
 * @param {object} [buffers] buffers from a previous evaluation, filled in place
 */
export function evaluate(spec, values, buffers) { // eslint-disable-line no-unused-vars
  throw new EvaluationError('molejo evaluation is not implemented yet');
}
