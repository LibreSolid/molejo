// molejo - analytic flexible parts for mechanical CAD
// Copyright (C) 2026 Luis Henrique Cassis Fagundes
// SPDX-License-Identifier: Apache-2.0

// Spec plus parameter values to vertex buffers.
//
// The twin of `python/molejo/evaluator.py`: the same conventions, the
// same arithmetic in the same order, the same error messages, held to it
// by the shared parity fixtures under `fixtures/`. What differs is only
// what the runtime forces -- positions are Float32 because that is what
// a three.js BufferGeometry wants, so the fixtures give this side a
// looser tolerance than the Python one.
//
// The conventions are pinned in design.md under "Sweep evaluation
// conventions" and restated in the Python twin's module docstring:
//
//   * the path starts at the origin with tangent +Z, the profile drawn in
//     world +X/+Y, transported rotation-minimizingly;
//   * circle profile vertex j of M at angle 2*pi*j/M, cos*x + sin*y;
//   * tessellation.path is a segment count N, so an open path has N + 1
//     rings; wall vertex ring*M + j, then the start-cap centre, then the
//     end-cap centre;
//   * faces run walls (ring-major, then j, two triangles a quad), then
//     the start-cap fan, then the end-cap fan, wound outward throughout.
//
// Because the counts are declared and never adaptive, the index is a
// function of the document alone. That is what makes the per-frame path
// cheap: a viewer hands back the buffers from the previous frame, the
// positions are refilled in place, and the index is not touched.

import { kindOf, parseSpec } from './spec.js';

/** Below this the cross product of two unit vectors is noise, not an axis. */
const PARALLEL = 1e-12;

/**
 * A spec cannot be evaluated at the given parameter values.
 *
 * The message names the offending element -- the parameter, the slot it is
 * referenced from -- so a caller can bind what is missing. Structural
 * faults are `SpecError`; this is what only values can reveal.
 */
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

// --- describing values in messages ------------------------------------

function describe(value) {
  if (typeof value !== 'number') return kindOf(value);
  if (Number.isNaN(value)) return 'nan';
  if (!Number.isFinite(value)) return value > 0 ? 'infinity' : '-infinity';
  return String(value);
}

// --- parameter resolution ----------------------------------------------

function resolve(slot, values, loc) {
  if (typeof slot === 'number') return slot;
  const name = slot.param;
  if (values === null || values === undefined || !(name in values)) {
    throw new EvaluationError(
      `values: no value bound for parameter '${name}', referenced at ${loc}`,
    );
  }
  const value = values[name];
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new EvaluationError(
      `values: parameter '${name}' must be a finite number, got ` +
        `${describe(value)} (referenced at ${loc})`,
    );
  }
  return value;
}

function resolveVector(slots, values, loc) {
  return slots.map((slot, axis) => resolve(slot, values, `${loc}[${axis}]`));
}

// --- frames -------------------------------------------------------------
//
// A frame is a point on the path plus the orthonormal triple the profile is
// drawn in: `x` and `y` span the profile plane, `tangent` is the sweep
// direction, and (x, y, tangent) is right-handed so that walking the profile
// from vertex j to j+1 turns counter-clockwise seen from ahead -- which is
// what makes the winding below outward without a per-face normal check.

/**
 * Where every path begins: the origin, looking up +Z, with the profile drawn
 * in the world's +X/+Y.
 */
export const START_FRAME = {
  origin: [0.0, 0.0, 0.0],
  x: [1.0, 0.0, 0.0],
  y: [0.0, 1.0, 0.0],
  tangent: [0.0, 0.0, 1.0],
};

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function norm(a) {
  return Math.sqrt(dot(a, a));
}

function apply(rotation, vector) {
  return [dot(rotation[0], vector), dot(rotation[1], vector), dot(rotation[2], vector)];
}

const IDENTITY = [
  [1.0, 0.0, 0.0],
  [0.0, 1.0, 0.0],
  [0.0, 0.0, 1.0],
];

/** Some unit vector orthogonal to `vector`, chosen deterministically. */
function perpendicular(vector) {
  let smallest = 0;
  for (let axis = 1; axis < 3; axis += 1) {
    if (Math.abs(vector[axis]) < Math.abs(vector[smallest])) smallest = axis;
  }
  const basis = [0.0, 0.0, 0.0];
  basis[smallest] = 1.0;
  const result = cross(vector, basis);
  const length = norm(result);
  return [result[0] / length, result[1] / length, result[2] / length];
}

function rodrigues(axis, angle) {
  const k = [
    [0.0, -axis[2], axis[1]],
    [axis[2], 0.0, -axis[0]],
    [-axis[1], axis[0], 0.0],
  ];
  const sine = Math.sin(angle);
  const versine = 1.0 - Math.cos(angle);
  const rotation = [];
  for (let row = 0; row < 3; row += 1) {
    rotation.push([]);
    for (let column = 0; column < 3; column += 1) {
      let square = 0.0;
      for (let inner = 0; inner < 3; inner += 1) square += k[row][inner] * k[inner][column];
      rotation[row].push(IDENTITY[row][column] + sine * k[row][column] + versine * square);
    }
  }
  return rotation;
}

/**
 * The rotation taking unit `source` onto unit `target` and turning about
 * nothing else -- the rotation-minimizing step of frame transport.
 *
 * Exactly the identity when the two directions are equal, which is what keeps
 * the frame constant along a straight path. Antiparallel directions have no
 * minimal rotation, so a deterministic perpendicular axis is chosen rather
 * than an arbitrary one.
 */
export function minimalRotation(source, target) {
  const axis = cross(source, target);
  const sine = norm(axis);
  const cosine = dot(source, target);
  if (sine <= PARALLEL) {
    if (cosine >= 0.0) return IDENTITY;
    return rodrigues(perpendicular(source), Math.PI);
  }
  return rodrigues(
    [axis[0] / sine, axis[1] / sine, axis[2] / sine],
    Math.atan2(sine, cosine),
  );
}

/**
 * `frame` carried onto a new tangent by the minimal rotation.
 *
 * The profile is not twisted about the tangent by the transport itself; any
 * twist a primitive wants (a helix's, say) is that primitive's own business
 * and is applied on top of this.
 */
export function transport(frame, tangent, origin) {
  const rotation = minimalRotation(frame.tangent, tangent);
  return {
    origin: origin === undefined ? frame.origin : origin,
    x: apply(rotation, frame.x),
    y: apply(rotation, frame.y),
    tangent,
  };
}

// --- profiles -----------------------------------------------------------

/** The profile as `count` [u, v] coordinates in the profile frame. */
function profilePoints(profile, values, count) {
  if (profile.type !== 'circle') {
    throw new NotImplementedError(
      `profile: the '${profile.type}' profile is not implemented yet; this ` +
        `molejo build evaluates 'circle' only`,
    );
  }
  const radius = resolve(profile.radius, values, 'profile.radius');
  if (radius <= 0.0) {
    throw new EvaluationError(
      `profile.radius: must be a positive number, got ${describe(radius)}`,
    );
  }
  const points = [];
  for (let j = 0; j < count; j += 1) {
    const angle = (2.0 * Math.PI * j) / count;
    points.push([radius * Math.cos(angle), radius * Math.sin(angle)]);
  }
  return points;
}

// --- paths --------------------------------------------------------------

/** The path as `segments + 1` ring centres and their profile axes. */
function samplePath(path, values, segments) {
  if (path.length !== 1) {
    throw new NotImplementedError(
      `path: this molejo build does not distribute tessellation.path across ` +
        `a multi-primitive path (${path.length} primitives) yet`,
    );
  }
  const primitive = path[0];
  if (primitive.type !== 'line') {
    throw new NotImplementedError(
      `path[0]: the '${primitive.type}' path primitive is not implemented yet; ` +
        `this molejo build evaluates 'line' only`,
    );
  }
  return sampleLine(primitive, values, segments, START_FRAME, 'path[0]');
}

/**
 * A straight run from the frame's origin to `to`.
 *
 * The frame is transported once, at the segment's start, and then held: a
 * line has one tangent, so a rotation-minimizing transport along it is the
 * identity.
 */
function sampleLine(primitive, values, segments, startFrame, loc) {
  const start = startFrame.origin;
  const end = resolveVector(primitive.to, values, `${loc}.to`);
  const direction = [end[0] - start[0], end[1] - start[1], end[2] - start[2]];
  const length = norm(direction);
  if (length <= 0.0) {
    throw new EvaluationError(
      `${loc}.to: a line must go somewhere; its end coincides with its start`,
    );
  }
  const frame = transport(startFrame, [
    direction[0] / length,
    direction[1] / length,
    direction[2] / length,
  ]);

  const centres = [];
  for (let ring = 0; ring <= segments; ring += 1) {
    const step = ring / segments;
    centres.push([
      start[0] + step * direction[0],
      start[1] + step * direction[1],
      start[2] + step * direction[2],
    ]);
  }
  return { centres, axes: centres.map(() => [frame.x, frame.y]) };
}

// --- buffers ------------------------------------------------------------

function writeIndex(index, rings, count) {
  let at = 0;
  // Walls, ring-major then j, two triangles a quad.
  for (let ring = 0; ring < rings - 1; ring += 1) {
    for (let j = 0; j < count; j += 1) {
      const following = (j + 1) % count;
      const a = ring * count + j;
      const b = ring * count + following;
      const c = b + count;
      const d = a + count;
      index[at] = a;
      index[at + 1] = b;
      index[at + 2] = c;
      index[at + 3] = a;
      index[at + 4] = c;
      index[at + 5] = d;
      at += 6;
    }
  }

  const startCentre = rings * count;
  const endCentre = startCentre + 1;
  const last = (rings - 1) * count;

  // The start cap winds backwards around ring 0, so it faces -tangent; the
  // end cap winds forwards around the last ring, facing +tangent.
  for (let j = 0; j < count; j += 1) {
    index[at] = startCentre;
    index[at + 1] = (j + 1) % count;
    index[at + 2] = j;
    at += 3;
  }
  for (let j = 0; j < count; j += 1) {
    index[at] = endCentre;
    index[at + 1] = last + j;
    index[at + 2] = last + ((j + 1) % count);
    at += 3;
  }
}

function checkBuffer(buffers, name, Kind, length) {
  const array = buffers[name];
  if (!(array instanceof Kind) || array.length !== length) {
    const got = ArrayBuffer.isView(array) ? `${array.length}` : kindOf(array);
    throw new EvaluationError(
      `buffers: ${name} must be a ${Kind.name} of ${length} numbers for this ` +
        `spec, got ${got}`,
    );
  }
}

// --- the evaluation -----------------------------------------------------

/**
 * Evaluate a molejo spec at the given parameter values.
 *
 * `values` is a plain `{name: number}` object; names the document does not
 * reference are ignored, so a consumer may hand over its whole machine
 * state. A name the document *does* reference and the object does not bind
 * is an error naming both the parameter and the slot: no partial or
 * repaired buffer is ever returned, and nothing is written into caller
 * buffers on the way to failing.
 *
 * Pass the return value of a previous evaluation of the *same* spec as
 * `buffers` and it is filled in place and handed back, allocating nothing:
 * the index cannot have changed, because the counts follow the document
 * alone.
 *
 * @param {string|object} spec
 * @param {object} values named scalar parameters
 * @param {object} [buffers] buffers from a previous evaluation of this spec
 * @returns {{positions: Float32Array, index: Uint32Array,
 *            vertexCount: number, triangleCount: number}}
 */
export function evaluate(spec, values, buffers) {
  const document = parseSpec(spec);

  if (document.loop) {
    throw new NotImplementedError(
      'loop: closed-loop paths are not implemented yet; this molejo build ' +
        'evaluates open paths only',
    );
  }

  const count = document.tessellation.profile;
  const segments = document.tessellation.path;

  // Everything a parameter can touch is resolved before a single vertex is
  // written, which is what makes "no partial output" true rather than hoped.
  const points = profilePoints(document.profile, values, count);
  const { centres, axes } = samplePath(document.path, values, segments);

  const rings = centres.length;
  const vertexCount = rings * count + 2;
  const triangleCount = 2 * (rings - 1) * count + 2 * count;

  let target = buffers;
  if (target === undefined || target === null) {
    target = {
      positions: new Float32Array(vertexCount * 3),
      index: new Uint32Array(triangleCount * 3),
      vertexCount,
      triangleCount,
    };
    writeIndex(target.index, rings, count);
  } else {
    checkBuffer(target, 'positions', Float32Array, vertexCount * 3);
    checkBuffer(target, 'index', Uint32Array, triangleCount * 3);
  }

  const positions = target.positions;
  let at = 0;
  for (let ring = 0; ring < rings; ring += 1) {
    const centre = centres[ring];
    const [x, y] = axes[ring];
    for (let j = 0; j < count; j += 1) {
      const [u, v] = points[j];
      positions[at] = centre[0] + u * x[0] + v * y[0];
      positions[at + 1] = centre[1] + u * x[1] + v * y[1];
      positions[at + 2] = centre[2] + u * x[2] + v * y[2];
      at += 3;
    }
  }
  for (const centre of [centres[0], centres[rings - 1]]) {
    positions[at] = centre[0];
    positions[at + 1] = centre[1];
    positions[at + 2] = centre[2];
    at += 3;
  }

  return target;
}
