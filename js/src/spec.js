// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// The molejo spec: schema parsing and structural validation.
//
// This is the twin of `python/molejo/spec.py`: the same rules, the same
// error messages, held to it by the shared fixtures under
// `fixtures/invalid/`. The browser side is evaluation-only -- it parses
// and validates the document the Python authoring layer emits, and never
// authors one -- so there is no constructor vocabulary here.
//
// Every numeric slot -- anywhere, coordinates included -- is either a JSON
// number or a parameter reference `{"param": "<name>"}`. Validation is
// structural and needs no parameter values; a reference to a parameter the
// caller has not bound is an evaluation error, not a structural one.

/** The spec version this implementation reads. */
export const SPEC_VERSION = 1;

/** The closed v1 profile vocabulary. */
export const PROFILE_TYPES = ['circle', 'polygon'];

/** The closed v1 path-primitive vocabulary. */
export const PRIMITIVE_TYPES = ['arc', 'helix', 'line', 'spline', 'wrap'];

/** The closed v1 tooth-flank vocabulary. */
export const TOOTH_FLANKS = ['trapezoid'];

const SLOT_FORM = '{"param": "<name>"}';

/** A document is not a valid molejo spec; the message names the offending
 * element by its position in the document. */
export class SpecError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SpecError';
  }
}

// --- describing values in messages ------------------------------------
//
// Messages must be byte-identical to the Python validator's, so values are
// described by JSON kind rather than by any runtime's type names.

function kindOf(value) {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'boolean') return 'a boolean';
  if (typeof value === 'number') return 'a number';
  if (typeof value === 'string') return 'a string';
  if (Array.isArray(value)) return 'an array';
  if (typeof value === 'object') return 'an object';
  return 'a value molejo does not understand';
}

function render(value) {
  return typeof value === 'number' ? String(value) : kindOf(value);
}

function quote(value) {
  return typeof value === 'string' ? `'${value}'` : kindOf(value);
}

function isObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isInteger(value) {
  return typeof value === 'number' && Number.isInteger(value);
}

function has(object, name) {
  return Object.prototype.hasOwnProperty.call(object, name);
}

// --- structural checks -------------------------------------------------

function checkObject(value, loc) {
  if (!isObject(value)) {
    throw new SpecError(`${loc}: must be an object, got ${kindOf(value)}`);
  }
}

function checkFields(object, loc, required, optional = []) {
  for (const name of required) {
    if (!has(object, name)) {
      throw new SpecError(`${loc}: missing required field '${name}'`);
    }
  }
  const allowed = new Set([...required, ...optional]);
  for (const name of Object.keys(object)) {
    if (!allowed.has(name)) {
      throw new SpecError(`${loc}: unknown field '${name}'`);
    }
  }
}

function checkSlot(value, loc) {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new SpecError(`${loc}: must be a finite number`);
    }
    return;
  }
  if (isObject(value)) {
    if (!has(value, 'param')) {
      throw new SpecError(
        `${loc}: must be a number or a parameter reference ${SLOT_FORM}, ` +
          "got an object with no 'param' field",
      );
    }
    for (const name of Object.keys(value)) {
      if (name !== 'param') {
        throw new SpecError(`${loc}: unknown field '${name}' in a parameter reference`);
      }
    }
    const name = value.param;
    if (typeof name !== 'string' || name === '') {
      throw new SpecError(
        `${loc}: a parameter reference needs a non-empty string name for ` +
          `'param', got ${render(name)}`,
      );
    }
    return;
  }
  throw new SpecError(
    `${loc}: must be a number or a parameter reference ${SLOT_FORM}, got ${kindOf(value)}`,
  );
}

function checkVector(value, loc, dimension) {
  if (!Array.isArray(value) || value.length !== dimension) {
    const got = Array.isArray(value) ? String(value.length) : kindOf(value);
    throw new SpecError(
      `${loc}: must be an array of ${dimension} numbers or parameter ` +
        `references, got ${got}`,
    );
  }
  value.forEach((item, index) => checkSlot(item, `${loc}[${index}]`));
}

function checkPoints(value, loc, dimension, minimum, what) {
  if (!Array.isArray(value) || value.length < minimum) {
    const got = Array.isArray(value) ? String(value.length) : kindOf(value);
    throw new SpecError(`${loc}: ${what} needs at least ${minimum} points, got ${got}`);
  }
  value.forEach((point, index) => checkVector(point, `${loc}[${index}]`, dimension));
}

function checkCount(value, loc, minimum = 1) {
  const label = minimum >= 1 ? 'a positive integer' : 'a non-negative integer';
  if (!isInteger(value) || value < minimum) {
    throw new SpecError(`${loc}: must be ${label}, got ${render(value)}`);
  }
}

// --- the document ------------------------------------------------------

/**
 * Validate a molejo document, throwing `SpecError` on the first offending
 * element. Returns undefined when the document is a valid spec.
 */
export function validate(document) {
  checkObject(document, 'spec');
  checkFields(document, 'spec', ['molejo', 'profile', 'path', 'tessellation'], ['loop']);

  const version = document.molejo;
  if (!isInteger(version)) {
    throw new SpecError(`spec.molejo: must be the integer 1, got ${render(version)}`);
  }
  if (version !== SPEC_VERSION) {
    throw new SpecError(
      `spec.molejo: unsupported spec version ${render(version)}; this ` +
        `implementation reads spec version ${SPEC_VERSION}`,
    );
  }

  checkProfile(document.profile, 'profile');
  checkPath(document.path, 'path');

  if (has(document, 'loop') && typeof document.loop !== 'boolean') {
    throw new SpecError(`loop: must be a boolean, got ${kindOf(document.loop)}`);
  }

  checkTessellation(document.tessellation, 'tessellation');
}

function checkProfile(profile, loc) {
  checkObject(profile, loc);
  if (!has(profile, 'type')) {
    throw new SpecError(`${loc}: missing required field 'type'`);
  }
  const kind = profile.type;
  if (kind === 'circle') {
    checkFields(profile, loc, ['type', 'radius']);
    checkSlot(profile.radius, `${loc}.radius`);
  } else if (kind === 'polygon') {
    checkFields(profile, loc, ['type', 'points']);
    checkPoints(profile.points, `${loc}.points`, 2, 3, 'a polygon');
  } else {
    throw new SpecError(
      `${loc}: unknown profile type ${quote(kind)}; expected one of ` +
        `${PROFILE_TYPES.join(', ')}`,
    );
  }
}

function checkPath(path, loc) {
  if (!Array.isArray(path) || path.length === 0) {
    const got = Array.isArray(path) ? '0' : kindOf(path);
    throw new SpecError(`${loc}: must be an array of at least 1 primitive, got ${got}`);
  }
  path.forEach((primitive, index) => checkPrimitive(primitive, `${loc}[${index}]`));
}

function checkPrimitive(primitive, loc) {
  checkObject(primitive, loc);
  if (!has(primitive, 'type')) {
    throw new SpecError(`${loc}: missing required field 'type'`);
  }
  const kind = primitive.type;

  if (kind === 'line') {
    checkFields(primitive, loc, ['type', 'to']);
    checkVector(primitive.to, `${loc}.to`, 3);
  } else if (kind === 'arc') {
    checkFields(primitive, loc, ['type', 'center', 'axis', 'angle']);
    checkVector(primitive.center, `${loc}.center`, 3);
    checkVector(primitive.axis, `${loc}.axis`, 3);
    checkSlot(primitive.angle, `${loc}.angle`);
  } else if (kind === 'helix') {
    checkFields(primitive, loc, ['type', 'radius', 'turns', 'height']);
    checkSlot(primitive.radius, `${loc}.radius`);
    checkSlot(primitive.turns, `${loc}.turns`);
    checkSlot(primitive.height, `${loc}.height`);
  } else if (kind === 'spline') {
    checkFields(primitive, loc, ['type', 'points']);
    checkPoints(primitive.points, `${loc}.points`, 3, 2, 'a spline');
  } else if (kind === 'wrap') {
    checkFields(primitive, loc, ['type', 'around'], ['teeth', 'anchor', 'phase']);
    checkWrapCircles(primitive.around, `${loc}.around`);
    if (has(primitive, 'teeth')) checkTeeth(primitive.teeth, `${loc}.teeth`);
    if (has(primitive, 'anchor')) checkAnchor(primitive.anchor, `${loc}.anchor`);
    if (has(primitive, 'phase')) checkSlot(primitive.phase, `${loc}.phase`);
  } else {
    throw new SpecError(
      `${loc}: unknown path primitive ${quote(kind)}; expected one of ` +
        `${PRIMITIVE_TYPES.join(', ')}`,
    );
  }
}

function checkWrapCircles(around, loc) {
  if (!Array.isArray(around) || around.length < 2) {
    const got = Array.isArray(around) ? String(around.length) : kindOf(around);
    throw new SpecError(`${loc}: a wrap needs at least 2 circles, got ${got}`);
  }
  around.forEach((circle, index) => {
    const circleLoc = `${loc}[${index}]`;
    checkObject(circle, circleLoc);
    checkFields(circle, circleLoc, ['center', 'radius']);
    checkVector(circle.center, `${circleLoc}.center`, 2);
    checkSlot(circle.radius, `${circleLoc}.radius`);
  });
}

function checkTeeth(teeth, loc) {
  checkObject(teeth, loc);
  checkFields(teeth, loc, ['pitch', 'height', 'flank', 'count']);
  checkSlot(teeth.pitch, `${loc}.pitch`);
  checkSlot(teeth.height, `${loc}.height`);
  if (!TOOTH_FLANKS.includes(teeth.flank)) {
    throw new SpecError(
      `${loc}.flank: unknown tooth flank ${quote(teeth.flank)}; expected one of ` +
        `${TOOTH_FLANKS.join(', ')}`,
    );
  }
  // The tooth count fixes topology, so it can never follow a parameter.
  checkCount(teeth.count, `${loc}.count`);
}

function checkAnchor(anchor, loc) {
  checkObject(anchor, loc);
  checkFields(anchor, loc, ['span', 'at']);
  checkCount(anchor.span, `${loc}.span`, 0);
  checkSlot(anchor.at, `${loc}.at`);
}

function checkTessellation(tessellation, loc) {
  checkObject(tessellation, loc);
  checkFields(tessellation, loc, ['path', 'profile']);
  // Declared and fixed: counts never follow geometry or a parameter, which
  // is what makes vertex correspondence across evaluations free.
  checkCount(tessellation.path, `${loc}.path`);
  checkCount(tessellation.profile, `${loc}.profile`);
}

// --- parsing -----------------------------------------------------------

/**
 * Parse and validate a molejo spec, given either JSON text or an already
 * parsed object. Returns the validated document with `loop` made explicit;
 * the caller's object is not modified.
 *
 * @param {string|object} source
 * @returns {object} the validated spec
 */
export function parseSpec(source) {
  let document = source;
  if (typeof source === 'string') {
    try {
      document = JSON.parse(source);
    } catch (error) {
      throw new SpecError(`spec: not valid JSON (${error.message})`);
    }
  }
  validate(document);
  return {
    molejo: document.molejo,
    profile: document.profile,
    path: document.path,
    loop: has(document, 'loop') ? document.loop : false,
    tessellation: document.tessellation,
  };
}

/**
 * The set of parameter names a document references. Whether those names are
 * bound is an evaluation-time question.
 *
 * @param {string|object} source
 * @returns {Set<string>}
 */
export function parameterNames(source) {
  const document = parseSpec(source);
  const names = new Set();
  collect(document, names);
  return names;
}

function collect(value, names) {
  if (Array.isArray(value)) {
    for (const item of value) collect(item, names);
  } else if (isObject(value)) {
    if (typeof value.param === 'string') {
      names.add(value.param);
      return;
    }
    for (const item of Object.values(value)) collect(item, names);
  }
}
