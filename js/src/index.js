// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// JavaScript evaluator: spec plus parameter values in, vertex buffers
// out. Spec parsing and validation live in ./spec.js; the
// evaluation of spec plus values into Float32 positions and a Uint32
// index lives in ./evaluate.js.

export {
  PRIMITIVE_TYPES,
  PROFILE_TYPES,
  SPEC_VERSION,
  SPEC_VERSIONS,
  TOOTH_FACES,
  TOOTH_FLANKS,
  WRAP_TURNS,
  SpecError,
  parameterNames,
  parseSpec,
  requiredVersion,
  validate,
} from './spec.js';

export { EvaluationError, NotImplementedError, evaluate } from './evaluate.js';

export const VERSION = '0.2.0';
