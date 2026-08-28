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
//   * tessellation.path is a segment count N spent on each *element* of the
//     path, a primitive's element count following the document alone (one
//     for a line, arc or helix; one span per declared point for a spline;
//     two per circle for a wrap), so a chain of k single-element
//     primitives has k*N + 1 rings and a joint's ring is sampled once, by
//     the primitive that leaves it; wall vertex ring*M + j, then the
//     start-cap centre, then the end-cap centre;
//   * faces run walls (ring-major, then j, two triangles a quad), then
//     the start-cap fan, then the end-cap fan, wound outward throughout;
//   * a closed loop drops the duplicate ring and both caps, so ring R-1's
//     quads wrap onto ring 0 and V = R*M, F = 2*R*M. Only a `wrap` path
//     is a loop today.
//
// Because the counts are declared and never adaptive, the index is a
// function of the document alone. That is what makes the per-frame path
// cheap: a viewer hands back the buffers from the previous frame, the
// positions are refilled in place, and the index is not touched.

import { kindOf, parseSpec } from './spec.js';

/** Below this the cross product of two unit vectors is noise, not an axis. */
const PARALLEL = 1e-12;

const TAU = 2.0 * Math.PI;

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

/** Vertex j of M at angle `2*pi*j/M`, at `cos*x + sin*y`. */
function circlePoints(profile, values, count) {
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

/**
 * The declared points, in order; the count is theirs, checked already.
 *
 * A polygon's coordinates are ordinary numeric slots, so a profile may be
 * driven by parameters like anything else. Their order is the author's:
 * counter-clockwise in the profile frame, as the circle's is, or the sweep
 * winds inward.
 */
function polygonPoints(profile, values) {
  return profile.points.map((point, index) =>
    resolveVector(point, values, `profile.points[${index}]`),
  );
}

/**
 * The profiles this build evaluates. One missing from here is valid v1
 * vocabulary that throws naming itself.
 */
const PROFILES = {
  circle: circlePoints,
  polygon: polygonPoints,
};

/** The profile as `count` [u, v] coordinates in the profile frame. */
function profilePoints(profile, values, count) {
  const sampler = PROFILES[profile.type];
  if (sampler === undefined) {
    throw new NotImplementedError(
      `profile: the '${profile.type}' profile is not implemented yet; this ` +
        `molejo build evaluates 'circle' and 'polygon' only`,
    );
  }
  return sampler(profile, values, count);
}

/**
 * Which profile vertices the teeth displace: those at the minimum x.
 *
 * Exact equality, not a tolerance: a section whose inner face is flat --
 * every belt's is -- has two or more vertices there, and one whose inner
 * face is rounded displaces a single vertex into a spike, which is
 * authorship rather than something molejo guesses at.
 */
function innerFace(points) {
  let least = points[0][0];
  for (const point of points) least = Math.min(least, point[0]);
  return points.map((point) => point[0] === least);
}

// --- paths --------------------------------------------------------------

/**
 * The path as `k * segments + 1` ring centres and their profile axes,
 * `segments` spent on each of the k primitives.
 *
 * `tessellation.path` is spent on every primitive rather than divided
 * among them: an arc-length-proportional split would make the ring count
 * follow a parameter, which declared tessellation forbids. A primitive
 * begins where its predecessor ended -- no primitive says where it starts
 * -- so the ring at a joint is sampled once, by the primitive that leaves
 * it, and the frame carried across is exactly the identity when the
 * tangents agree.
 */
function samplePath(path, values, segments) {
  let frame = START_FRAME;
  const centres = [];
  const axes = [];
  for (let index = 0; index < path.length; index += 1) {
    const primitive = path[index];
    const loc = `path[${index}]`;
    const sampled = SAMPLERS[primitive.type](primitive, values, segments, frame, loc);
    frame = sampled.frame;
    // The last ring of every primitive but the final one is the joint
    // ring, and belongs to the primitive that leaves it. A wrap returns
    // the rings of a closed loop, whose last ring is ring 0 itself, so
    // the count comes from the sampler rather than from `segments`.
    const rings =
      index === path.length - 1 ? sampled.centres.length : sampled.centres.length - 1;
    for (let ring = 0; ring < rings; ring += 1) {
      centres.push(sampled.centres[ring]);
      axes.push(sampled.axes[ring]);
    }
  }
  return { centres, axes };
}

/**
 * The profile axes along a turning primitive, ring by ring.
 *
 * Transport is composed step by step rather than taken in one jump from
 * the incoming frame: that is the discrete rotation-minimizing frame, and
 * it is what a curve turning under the profile means. For an arc the two
 * agree exactly -- every tangent lies in the plane perpendicular to the
 * arc's axis, so every step turns about that same axis -- and for a
 * helix, whose tangents trace a cone, only the composition is
 * rotation-minimizing.
 */
function carried(startFrame, centres, tangents) {
  let frame = startFrame;
  const axes = [];
  for (let ring = 0; ring < centres.length; ring += 1) {
    frame = transport(frame, tangents[ring], centres[ring]);
    axes.push([frame.x, frame.y]);
  }
  return { axes, frame };
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
  const frame = transport(
    startFrame,
    [direction[0] / length, direction[1] / length, direction[2] / length],
    end,
  );

  const centres = [];
  for (let ring = 0; ring <= segments; ring += 1) {
    const step = ring / segments;
    centres.push([
      start[0] + step * direction[0],
      start[1] + step * direction[1],
      start[2] + step * direction[2],
    ]);
  }
  return { centres, axes: centres.map(() => [frame.x, frame.y]), frame };
}

/**
 * The current point turned about the axis line through `center`.
 *
 * Only the component of `start - center` across the axis turns, so
 * `center` names an axis line rather than a point the arc must reach. Ring
 * i of N sits at `phi = i*angle/N` on that circle, and the tangent is the
 * circle's, signed by the direction of the turn.
 */
function sampleArc(primitive, values, segments, startFrame, loc) {
  const center = resolveVector(primitive.center, values, `${loc}.center`);
  const axisSlot = resolveVector(primitive.axis, values, `${loc}.axis`);
  const angle = resolve(primitive.angle, values, `${loc}.angle`);

  const length = norm(axisSlot);
  if (length <= 0.0) {
    throw new EvaluationError(
      `${loc}.axis: an arc needs an axis to turn about; its axis has no direction`,
    );
  }
  const axis = [axisSlot[0] / length, axisSlot[1] / length, axisSlot[2] / length];

  const origin = startFrame.origin;
  const spoke = [origin[0] - center[0], origin[1] - center[1], origin[2] - center[2]];
  const along = dot(spoke, axis);
  const axial = [axis[0] * along, axis[1] * along, axis[2] * along];
  const across = [spoke[0] - axial[0], spoke[1] - axial[1], spoke[2] - axial[2]];
  const radius = norm(across);
  if (radius <= 0.0) {
    throw new EvaluationError(
      `${loc}.center: an arc needs a radius to turn on; its start point lies ` +
        `on its axis`,
    );
  }
  if (angle === 0.0) {
    throw new EvaluationError(
      `${loc}.angle: an arc must turn somewhere; its angle is 0`,
    );
  }

  const radial = [across[0] / radius, across[1] / radius, across[2] / radius];
  const tangential = cross(axis, radial);
  const sign = angle > 0.0 ? 1.0 : -1.0;

  const centres = [];
  const tangents = [];
  for (let ring = 0; ring <= segments; ring += 1) {
    const turn = (angle * ring) / segments;
    const cosine = Math.cos(turn);
    const sine = Math.sin(turn);
    centres.push([
      center[0] + axial[0] + radius * (cosine * radial[0] + sine * tangential[0]),
      center[1] + axial[1] + radius * (cosine * radial[1] + sine * tangential[1]),
      center[2] + axial[2] + radius * (cosine * radial[2] + sine * tangential[2]),
    ]);
    tangents.push([
      sign * (cosine * tangential[0] - sine * radial[0]),
      sign * (cosine * tangential[1] - sine * radial[1]),
      sign * (cosine * tangential[2] - sine * radial[2]),
    ]);
  }
  return { centres, ...carried(startFrame, centres, tangents) };
}

/**
 * A helix winding about the incoming tangent, from the current point.
 *
 * Its axis is the line through `origin - radius * x` along the tangent, so
 * the helix starts exactly where the path is; it winds right-handed (the
 * frame's x turning toward its y) and advances `height` over `turns`
 * turns. The speed is constant, so rings uniform in the turn parameter are
 * uniform in arc length.
 */
function sampleHelix(primitive, values, segments, startFrame, loc) {
  const radius = resolve(primitive.radius, values, `${loc}.radius`);
  const turns = resolve(primitive.turns, values, `${loc}.turns`);
  const height = resolve(primitive.height, values, `${loc}.height`);

  if (radius <= 0.0) {
    throw new EvaluationError(
      `${loc}.radius: must be a positive number, got ${describe(radius)}`,
    );
  }
  const around = 2.0 * Math.PI * turns * radius;
  const speed = Math.hypot(around, height);
  if (speed <= 0.0) {
    throw new EvaluationError(
      `${loc}: a helix must go somewhere; it makes 0 turns and rises 0`,
    );
  }

  const { origin, x, y, tangent } = startFrame;
  const axisPoint = [
    origin[0] - radius * x[0],
    origin[1] - radius * x[1],
    origin[2] - radius * x[2],
  ];

  const centres = [];
  const tangents = [];
  for (let ring = 0; ring <= segments; ring += 1) {
    const step = ring / segments;
    const turn = 2.0 * Math.PI * turns * step;
    const cosine = Math.cos(turn);
    const sine = Math.sin(turn);
    const rise = height * step;
    const centre = [];
    const direction = [];
    for (let axis = 0; axis < 3; axis += 1) {
      centre.push(
        axisPoint[axis] +
          radius * (cosine * x[axis] + sine * y[axis]) +
          rise * tangent[axis],
      );
      direction.push(
        (around * (-sine * x[axis] + cosine * y[axis]) + height * tangent[axis]) /
          speed,
      );
    }
    centres.push(centre);
    tangents.push(direction);
  }
  return { centres, ...carried(startFrame, centres, tangents) };
}

/**
 * A declared end tangent as a unit direction, or the fallback.
 *
 * What the author declares is where the curve points; the length is
 * ignored, exactly as an arc's axis is, because the Hermite speed at an end
 * comes from the adjacent chord -- the same scale the Catmull-Rom interior
 * tangents carry.
 */
function splineDirection(declared, fallback, loc, what) {
  if (declared === null) return fallback;
  const length = norm(declared);
  if (length <= 0.0) {
    throw new EvaluationError(
      `${loc}: a spline's ${what} tangent needs a direction; it has no length`,
    );
  }
  return [declared[0] / length, declared[1] / length, declared[2] / length];
}

/**
 * A cubic Hermite chain through the declared points, clamped at its ends.
 *
 * The spline begins where the path has reached, so `points` are what it
 * runs through and toward: with that start P0 and the declared P1 … Pn it
 * has n spans, each spent `segments` segments, and the ring at a joint
 * belongs to the span that leaves it.
 *
 * The tangent it carries at each point is Catmull-Rom inside
 * (`m_i = (P_{i+1} - P_{i-1})/2`) and declared at the two ends, scaled to
 * the adjacent chord. An absent `start_tangent` means the incoming tangent
 * -- so a lead-in hands over without a kink -- and an absent `end_tangent`
 * means the final chord. Neither default is a value the document could
 * have written, because both follow parameter values.
 *
 * Consecutive spans share the tangent vector at the point between them, so
 * the curve is C1 across every interior point by construction rather than
 * by the author's care.
 */
function sampleSpline(primitive, values, segments, startFrame, loc) {
  const points = [startFrame.origin];
  primitive.points.forEach((point, index) => {
    points.push(resolveVector(point, values, `${loc}.points[${index}]`));
  });
  const spans = points.length - 1;

  const declaredStart =
    primitive.start_tangent === undefined
      ? null
      : resolveVector(primitive.start_tangent, values, `${loc}.start_tangent`);
  const declaredEnd =
    primitive.end_tangent === undefined
      ? null
      : resolveVector(primitive.end_tangent, values, `${loc}.end_tangent`);

  const chords = [];
  for (let index = 0; index < spans; index += 1) {
    const here = points[index];
    const there = points[index + 1];
    const chord = norm([there[0] - here[0], there[1] - here[1], there[2] - here[2]]);
    if (chord <= 0.0) {
      throw new EvaluationError(
        `${loc}.points[${index}]: a spline must go somewhere; points[${index}] ` +
          `coincides with the point before it`,
      );
    }
    chords.push(chord);
  }

  const tangentsAt = [];
  const start = splineDirection(
    declaredStart,
    startFrame.tangent,
    `${loc}.start_tangent`,
    'start',
  );
  tangentsAt.push(start.map((axis) => chords[0] * axis));
  for (let index = 1; index < spans; index += 1) {
    const before = points[index - 1];
    const after = points[index + 1];
    const tangent = [
      0.5 * (after[0] - before[0]),
      0.5 * (after[1] - before[1]),
      0.5 * (after[2] - before[2]),
    ];
    if (norm(tangent) <= 0.0) {
      throw new EvaluationError(
        `${loc}.points[${index - 1}]: a spline needs a direction where it turns; ` +
          `the points on either side of points[${index - 1}] coincide`,
      );
    }
    tangentsAt.push(tangent);
  }
  if (declaredEnd === null) {
    const last = points[spans];
    const before = points[spans - 1];
    tangentsAt.push([last[0] - before[0], last[1] - before[1], last[2] - before[2]]);
  } else {
    const end = splineDirection(declaredEnd, null, `${loc}.end_tangent`, 'end');
    tangentsAt.push(end.map((axis) => chords[spans - 1] * axis));
  }

  const centres = [];
  const tangents = [];
  for (let index = 0; index < spans; index += 1) {
    // The last span alone contributes its final ring: a joint's ring
    // belongs to the span that leaves it.
    const rings = index === spans - 1 ? segments + 1 : segments;
    const here = points[index];
    const there = points[index + 1];
    const leaving = tangentsAt[index];
    const arriving = tangentsAt[index + 1];
    for (let ring = 0; ring < rings; ring += 1) {
      const t = ring / segments;
      const square = t * t;
      const cube = square * t;
      // The Hermite basis is exactly (1, 0, 0, 0) at t = 0 and exactly
      // (0, 0, 1, 0) at t = 1, so every declared point is hit bit for bit.
      const h00 = 2.0 * cube - 3.0 * square + 1.0;
      const h10 = cube - 2.0 * square + t;
      const h01 = 3.0 * square - 2.0 * cube;
      const h11 = cube - square;
      const g00 = 6.0 * square - 6.0 * t;
      const g10 = 3.0 * square - 4.0 * t + 1.0;
      const g11 = 3.0 * square - 2.0 * t;
      const centre = [];
      const velocity = [];
      for (let axis = 0; axis < 3; axis += 1) {
        centre.push(
          h00 * here[axis] + h10 * leaving[axis] + h01 * there[axis] + h11 * arriving[axis],
        );
        velocity.push(
          g00 * (here[axis] - there[axis]) + g10 * leaving[axis] + g11 * arriving[axis],
        );
      }
      const speed = norm(velocity);
      if (speed <= 0.0) {
        // A cusp the author asked for. Refused rather than divided by,
        // because a NaN mesh is not the deterministic and visibly wrong a
        // kinked joint is.
        throw new EvaluationError(
          `${loc}: a spline must be going somewhere at every ring; its tangent ` +
            `vanishes on the span to points[${index}]`,
        );
      }
      centres.push(centre);
      tangents.push(velocity.map((axis) => axis / speed));
    }
  }

  return { centres, ...carried(startFrame, centres, tangents) };
}

/**
 * The belt's own geometry: ring centres, tangents, and arc lengths.
 *
 * A wrap is planar -- it lies in the world XY plane, because its circles
 * are declared there -- and it runs the external tangents, clockwise seen
 * from +Z, touching every circle along its outward normal. For consecutive
 * circles at distance L with radii r and r':
 *
 *     n = delta*chat + sqrt(1 - delta^2)*rot90(chat),  delta = (r - r')/L
 *
 * and the direction of travel is `(n_y, -n_x)`. The elements of the loop
 * are span 0, the arc about circle 1, span 1, … and finally the arc about
 * circle 0, each spent `segments` rings; the loop's origin is where the
 * belt leaves circle 0.
 */
function wrapGeometry(primitive, values, segments, loc) {
  const circles = primitive.around;
  const count = circles.length;

  const centres = [];
  const radii = [];
  for (let index = 0; index < count; index += 1) {
    centres.push(
      resolveVector(circles[index].center, values, `${loc}.around[${index}].center`),
    );
    const radius = resolve(
      circles[index].radius,
      values,
      `${loc}.around[${index}].radius`,
    );
    if (radius <= 0.0) {
      throw new EvaluationError(
        `${loc}.around[${index}].radius: must be a positive number, got ` +
          `${describe(radius)}`,
      );
    }
    radii.push(radius);
  }

  const normals = [];
  for (let index = 0; index < count; index += 1) {
    const following = (index + 1) % count;
    const span = [
      centres[following][0] - centres[index][0],
      centres[following][1] - centres[index][1],
    ];
    const length = Math.sqrt(span[0] * span[0] + span[1] * span[1]);
    const gap = radii[index] - radii[following];
    if (length <= Math.abs(gap)) {
      throw new EvaluationError(
        `${loc}.around[${following}]: a wrap needs an external tangent between ` +
          `consecutive circles; around[${index}] and around[${following}] are too ` +
          `close for one`,
      );
    }
    const direction = [span[0] / length, span[1] / length];
    const delta = gap / length;
    const sideways = Math.sqrt(1.0 - delta * delta);
    normals.push([
      delta * direction[0] + sideways * -direction[1],
      delta * direction[1] + sideways * direction[0],
    ]);
  }

  const ringCentres = [];
  const tangents = [];
  const stations = [];
  const spanStarts = [];
  let travelled = 0.0;
  for (let index = 0; index < count; index += 1) {
    const following = (index + 1) % count;
    const normal = normals[index];

    // The tangent span, from circle `index` to circle `following`.
    const start = [
      centres[index][0] + radii[index] * normal[0],
      centres[index][1] + radii[index] * normal[1],
    ];
    const end = [
      centres[following][0] + radii[following] * normal[0],
      centres[following][1] + radii[following] * normal[1],
    ];
    const reach = [end[0] - start[0], end[1] - start[1]];
    const length = Math.sqrt(reach[0] * reach[0] + reach[1] * reach[1]);
    spanStarts.push(travelled);
    for (let ring = 0; ring < segments; ring += 1) {
      const step = ring / segments;
      ringCentres.push([start[0] + step * reach[0], start[1] + step * reach[1], 0.0]);
      tangents.push([normal[1], -normal[0], 0.0]);
      stations.push(travelled + step * length);
    }
    travelled += length;

    // The arc about circle `following`, clockwise from the normal the
    // belt arrives on to the one it leaves on.
    const arrival = Math.atan2(normal[1], normal[0]);
    const departure = Math.atan2(normals[following][1], normals[following][0]);
    const turn = (((arrival - departure) % TAU) + TAU) % TAU;
    const radius = radii[following];
    for (let ring = 0; ring < segments; ring += 1) {
      const step = ring / segments;
      const angle = arrival - turn * step;
      const cosine = Math.cos(angle);
      const sine = Math.sin(angle);
      ringCentres.push([
        centres[following][0] + radius * cosine,
        centres[following][1] + radius * sine,
        0.0,
      ]);
      tangents.push([sine, -cosine, 0.0]);
      stations.push(travelled + step * (radius * turn));
    }
    travelled += radius * turn;
  }

  return { centres: ringCentres, tangents, stations, length: travelled, spanStarts };
}

/**
 * A belt around ordered circles, as a closed planar loop.
 *
 * The one primitive that says where it is, so it starts in a frame of its
 * own rather than the one it is handed -- which is why validation keeps it
 * alone in its path. Local x is the outward normal and local y is world
 * +Z, and the belt circulates clockwise seen from +Z so that triple is
 * right-handed and the pinned outward winding needs no special case.
 * Transport is then the ordinary ring-by-ring one: the path is planar, so
 * every minimal rotation is about +/-Z and the frame comes back to the
 * start frame at the seam.
 */
function sampleWrap(primitive, values, segments, startFrame, loc) {
  const wrap = wrapGeometry(primitive, values, segments, loc);
  const tangent = wrap.tangents[0];
  const start = {
    origin: wrap.centres[0],
    x: [-tangent[1], tangent[0], 0.0],
    y: [0.0, 0.0, 1.0],
    tangent,
  };
  return { centres: wrap.centres, ...carried(start, wrap.centres, wrap.tangents) };
}

/**
 * How far each ring's inner face is pushed toward the circles.
 *
 * Teeth are a periodic trapezoid in arc length whose period is the loop's
 * length over the declared count: an integer count over the whole loop is
 * what closes the pattern at the seam, and what keeps a moving idler
 * changing the tooth pitch *length* rather than the tooth count. One
 * period is a quarter crest centred on the pattern origin, a quarter ramp,
 * a quarter root and a quarter ramp back. The declared `teeth.pitch` is
 * the nominal pitch of the belt standard and is not read here (see
 * design.md, "The wrap").
 *
 * The origin is `anchor` (a distance along a named tangent span, so a belt
 * clamped to a carriage keeps its teeth meshed as the carriage runs), or
 * `phase` (belt travel from the wrap's own origin), or the wrap's own
 * origin when the document names neither.
 */
function wrapDisplacement(primitive, values, segments, loc) {
  const teeth = primitive.teeth;
  const anchor = primitive.anchor;
  if (teeth === undefined && anchor === undefined && primitive.phase === undefined) {
    return null;
  }

  const wrap = wrapGeometry(primitive, values, segments, loc);
  let origin = 0.0;
  if (anchor !== undefined) {
    origin = wrap.spanStarts[anchor.span] + resolve(anchor.at, values, `${loc}.anchor.at`);
  } else if (primitive.phase !== undefined) {
    origin = resolve(primitive.phase, values, `${loc}.phase`);
  }

  if (teeth === undefined) return null;
  const height = resolve(teeth.height, values, `${loc}.teeth.height`);
  if (height < 0.0) {
    throw new EvaluationError(
      `${loc}.teeth.height: must be a non-negative number, got ${describe(height)}`,
    );
  }

  const period = wrap.length / teeth.count;
  return wrap.stations.map((station) => {
    const fraction = ((((station - origin) / period) % 1.0) + 1.0) % 1.0;
    const distance = Math.min(fraction, 1.0 - fraction);
    return height * Math.min(1.0, Math.max(0.0, (0.375 - distance) * 4.0));
  });
}

/**
 * The whole v1 path vocabulary, each primitive with its sampler. There is
 * no fallback here because there is nothing left to fall back from:
 * validation refuses a primitive this table does not name.
 */
const SAMPLERS = {
  line: sampleLine,
  arc: sampleArc,
  helix: sampleHelix,
  spline: sampleSpline,
  wrap: sampleWrap,
};

// --- buffers ------------------------------------------------------------

function writeIndex(index, rings, count, loop) {
  let at = 0;
  // Walls, ring-major then j, two triangles a quad. A loop has one more
  // band than an open sweep: its last ring's quads wrap onto ring 0,
  // which is what closes the belt without a duplicate ring.
  const bands = loop ? rings : rings - 1;
  for (let ring = 0; ring < bands; ring += 1) {
    const onward = ((ring + 1) % rings) * count;
    for (let j = 0; j < count; j += 1) {
      const following = (j + 1) % count;
      const a = ring * count + j;
      const b = ring * count + following;
      const c = onward + following;
      const d = onward + j;
      index[at] = a;
      index[at + 1] = b;
      index[at + 2] = c;
      index[at + 3] = a;
      index[at + 4] = c;
      index[at + 5] = d;
      at += 6;
    }
  }

  // No open end, so nothing to cap: the walls already close.
  if (loop) return;

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

  // A wrap is a closed loop and validation has already made its document
  // say so; closing a chain of other primitives waits on the end frame,
  // which a rotation-minimizing transport does not bring back in general.
  const loop = document.path[0].type === 'wrap';
  if (document.loop && !loop) {
    throw new NotImplementedError(
      'loop: closing a chain of primitives is not implemented yet; this molejo ' +
        "build closes the loop of a 'wrap' path only",
    );
  }

  const count = document.tessellation.profile;
  const segments = document.tessellation.path;

  // Everything a parameter can touch is resolved before a single vertex is
  // written, which is what makes "no partial output" true rather than hoped.
  const points = profilePoints(document.profile, values, count);
  const { centres, axes } = samplePath(document.path, values, segments);
  const displacement = loop
    ? wrapDisplacement(document.path[0], values, segments, 'path[0]')
    : null;
  const inner = displacement === null ? null : innerFace(points);

  const rings = centres.length;
  const vertexCount = loop ? rings * count : rings * count + 2;
  const triangleCount = loop
    ? 2 * rings * count
    : 2 * (rings - 1) * count + 2 * count;

  let target = buffers;
  if (target === undefined || target === null) {
    target = {
      positions: new Float32Array(vertexCount * 3),
      index: new Uint32Array(triangleCount * 3),
      vertexCount,
      triangleCount,
    };
    writeIndex(target.index, rings, count, loop);
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
      const [across, v] = points[j];
      // A tooth pushes the profile's inner face toward the negative
      // local x and leaves every other vertex where it is.
      const u =
        displacement !== null && inner[j] ? across - displacement[ring] : across;
      positions[at] = centre[0] + u * x[0] + v * y[0];
      positions[at + 1] = centre[1] + u * x[1] + v * y[1];
      positions[at + 2] = centre[2] + u * x[2] + v * y[2];
      at += 3;
    }
  }
  if (!loop) {
    for (const centre of [centres[0], centres[rings - 1]]) {
      positions[at] = centre[0];
      positions[at + 1] = centre[1];
      positions[at + 2] = centre[2];
      at += 3;
    }
  }

  return target;
}
