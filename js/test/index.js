// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// Suite entry point. Node's test runner (24.x) executes a directory
// argument as a module rather than discovering the files inside it, so
// `node --test js/test/` lands here; this file pulls in every test
// module. Add new suites to this list.

import './spec.test.js';
import './invalid-fixtures.test.js';
import './evaluate.test.js';
import './parity-fixtures.test.js';
