// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// JavaScript evaluator: spec plus parameter values in, vertex buffers
// out. Spec version 1 parsing and validation live in ./spec.js; the
// evaluation of spec plus values into Float32 positions and a Uint32
// index lives in ./evaluate.js.

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

export { EvaluationError, NotImplementedError, evaluate } from './evaluate.js';

export const VERSION = '0.0.1-dev.0';
