// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// JavaScript evaluator: spec plus parameter values in, vertex buffers
// out. Spec version 1 parsing and validation are implemented (see
// ./spec.js); mesh evaluation is not, and is the next increment in the
// repository's openspec/ records.

export {
  PRIMITIVE_TYPES,
  PROFILE_TYPES,
  SPEC_VERSION,
  TOOTH_FLANKS,
  SpecError,
  parameterNames,
  parseSpec,
  validate,
} from './spec.js';

export const VERSION = '0.0.1-dev.0';

/**
 * Evaluate a spec at the given parameter values into vertex buffers.
 *
 * @param {string|object} spec
 * @param {object} values named scalar parameters
 * @param {object} [buffers] caller-provided buffers to fill in place
 */
export function evaluate(spec, values, buffers) { // eslint-disable-line no-unused-vars
  throw new Error('molejo evaluation is not implemented yet');
}
