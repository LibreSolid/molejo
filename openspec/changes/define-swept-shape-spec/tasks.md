## 1. Spec schema and validation

- [x] 1.1 Red: a schema document with an unknown primitive, an unknown
      profile, a profile that cannot close (a polygon of fewer than
      three points), or missing tessellation counts is rejected with an
      error naming the offending slot. A dangling parameter reference
      is *not* a structural error — it is an evaluation error, and the
      schema model instead exposes the referenced names (see
      design.md, "Validation is structural, total, and locates the
      offending element").
- [x] 1.2 Implement the schema model and validator in Python
      (`molejo.spec`): version tag, profile, path chain, parameter
      references, declared tessellation counts.
- [x] 1.3 Implement schema parsing and the same validations in JS;
      shared invalid-document fixtures under `fixtures/invalid/` run
      red on both sides first.
- [x] 1.4 Red: Python authoring constructors (`Shape`, profiles, path
      primitives, `P`) serialize to exactly the canonical JSON of the
      equivalent hand-written spec; a parameter reference used in
      arithmetic raises.
- [x] 1.5 Implement the authoring layer over the schema model.

## 2. First vertical slice: circle profile, line path

- [x] 2.1 Red (Python): a cylinder spec (circle profile swept along one
      line) evaluates to a watertight mesh with exactly the declared
      vertex count, capped ends, and the analytically correct volume
      within tolerance.
- [x] 2.2 Implement profile evaluation, frame transport along a line,
      capping, and mesh assembly in Python.
- [x] 2.3 Red (Python): the same spec with the line length as
      `{"param": "length"}` evaluates differently under two parameter
      bindings and identically under repeated identical bindings.
- [x] 2.4 Implement parameter resolution.
- [x] 2.5 First parity fixture: the cylinder spec, two parameter
      bindings, expected arrays; JS side red, then implement the JS
      twin (profile, line, caps) until parity passes.
- [x] 2.6 STL export from the Python evaluation (binary STL bytes),
      asserted watertight by an independent reader.

## 3. Arc and helix

- [x] 3.1 Red: arc path fixture (quarter-bend tube) — counts, ordering,
      endpoint frames continuous with adjoining line segments.
- [x] 3.2 Implement `arc` in Python, then JS, to fixture parity.
- [x] 3.3 Red: helix fixture — a spring at two pitches bound via
      `{"param": "pitch"}`; wire cross-section stays circular (no axial
      shear of the profile), coil count fixed.
- [x] 3.4 Implement `helix` in Python, then JS, to fixture parity.

## 4. Wrap and spline

- [x] 4.1 Settle the `wrap` signature against the belt validation case
      (ordered circles, side flags, phase, open-span anchor); record
      the decision in design.md before implementing. Settled with it:
      the closed-loop join and what `tessellation.profile` means for a
      polygon, which the belt is the first shape to need (see
      design.md, "The wrap, its teeth, the polygon profile, and the
      closed loop").
- [x] 4.2 Red: wrap fixture — closed loop around three circles;
      tangency continuity; phase parameter circulates the profile
      pattern without changing counts. Two fixtures: the three-pulley
      belt (moving idler and circulating phase) and the carriage belt
      (the Metamaquina2 geometry, teeth anchored to a running
      carriage).
- [x] 4.3 Implement `wrap` in Python, then JS, to fixture parity, with
      the polygon profile and the closed-loop join it needs.
- [x] 4.4 Settle the spline flavor against the loom validation case;
      record the decision in design.md. Settled: a cubic Hermite chain
      through the declared points, Catmull-Rom inside and clamped at the
      ends, because the loom needs interpolation *and* end-direction
      control and those are the same curve. Settled with it: what
      `points` mean for a primitive that does not declare its start, the
      two tangent slots and their defaults, and `tessellation.path` as a
      count per *element* (see design.md, "The spline, its end tangents,
      and the loom").
- [x] 4.5 Red: spline fixture — a loom run whose end point and tangents
      are parameter references in three names (x, y, z); evaluation
      cost measured independent of parameter count. Two fixtures: the
      filament loom (head bound in three names, two sag waypoints,
      clamped at both ends) and the loom lead-in (a spline continuing a
      line without a kink). The cost claim is asserted structurally —
      every numeric slot read exactly once, a fully-parametric loom and
      its literal twin reading the same slots to the same bits — rather
      than measured.
- [x] 4.6 Implement `spline` in Python, then JS, to fixture parity.

## 5. Parity harness

- [x] 5.1 Python suite runs every fixture in `fixtures/`; JS suite runs
      the same files; a fixture present on one side and missing from
      the other fails that side's suite.
- [x] 5.2 Fixture format documents counts-and-ordering exactness and
      per-fixture coordinate tolerance; one deliberately perturbed
      expectation proves both suites actually compare.

## 6. B-rep evaluator (exact shapes)

- [x] 6.1 Red: with the `brep` extra installed, the cylinder spec
      evaluates to a single closed solid whose volume matches the
      analytic volume; without the extra, invoking the B-rep evaluator
      raises naming the extra and mesh evaluation still works. The
      absence is simulated with an import hook, because a checkout that
      has the extra would otherwise never test the boundary.
- [x] 6.2 Implement profile wires, line/arc path edges, the pipe-shell
      sweep with the pinned frame convention, and caps; assert
      line/arc sweeps yield analytic surfaces only. Settled with it: the
      OCCT binding (OCP, as the `brep` extra), the trihedron law
      (corrected Frenet) and its honest limits, and the belt as a prism
      rather than a sweep -- the one construction that can carry teeth,
      exact but for the Archimedean spiral a ramp traces where it
      crosses an arc (see design.md, "The OCCT binding, the trihedron
      law, and what a belt's teeth cost").
- [x] 6.3 Red: helix and spline sweeps produce closed solids agreeing
      with their mesh fixtures on volume and area within fixture
      tolerance, with the approximation tolerance declared on the
      result.
- [x] 6.4 Implement helix (curve-on-cylinder) and spline (B-spline
      curve) path construction. The spline is one degree-3 B-spline with
      double interior knots and 2n+2 poles, not a Bezier chain, so the
      kernel carries the C1 continuity the curve actually has.
- [x] 6.5 Property-parity pass: the parity suite checks every
      fixture's expected-mesh volume and area against the B-rep
      evaluation when the extra is installed. The fixture format grows a
      per-fixture `brep` property tolerance, because a faceted mesh
      understates the smooth solid it samples and the coordinate
      tolerances say nothing about that; the gap is asserted one-sided
      and the same solid is held to an independent closed form at 1e-6.

## 7. Distribution

- [x] 7.1 `python -m build` produces an installable wheel from
      `python/`; a clean-venv install (no extras) imports `molejo` and
      evaluates the cylinder fixture. `scripts/check-dist-python` is the
      dry-run: it builds both artifacts, checks what they carry, and
      installs the wheel and the sdist into throwaway venvs, smoking each
      from a throwaway directory so no import can reach the checkout.
- [x] 7.2 `npm pack` from `js/` produces an installable package; a
      scratch consumer imports it and evaluates the cylinder fixture.
      `scripts/check-dist-js` is the dry-run, and `scripts/check-dist`
      runs both halves — the two packages release together, so they are
      checked together.
- [x] 7.3 Version discipline recorded in README: package versions carry
      the spec version they implement, the two packages release together
      for a spec version, and publishing itself waits for the pilot's
      explicit go. No script in this repository uploads anything.

## 8. Validation cases (consumer-side, evidence recorded here)

- [x] 8.1 Valve spring: helix spec driven by one lift parameter renders
      and animates in the consuming framework's viewer, and its B-rep
      evaluation passes an exact-shape assertion in the consumer's
      test suite.
  - Evidence (2026-08-29): solid-node's `flexible-leaf-node` change
      adapts molejo as its flexible leaf (`MolejoNode`, port-fed
      parameters, spec-carried documents). Viewer: headless-Chromium
      drive of the framework's spring fixture — `setDriver(lift, 12)`
      compresses 50.749 mm → 38.776 mm with vertex count, index and
      backing `Float32Array` identical (in-place refill observed live).
      Consumer suite: v8-engine branch `molejo` (`ef0b046`) models all
      16 valve springs; at full lift each asserts non-intersection
      against valve, retainer and head on OCCT solids from
      `molejo.brep`, with AABBs proven overlapping so only the exact
      kernel can answer. 36/36 green.
- [x] 8.2 Belt: wrap spec with circulating phase and carriage-anchored
      span validates against the belt case.
  - Evidence (2026-08-29): Metamaquina2 branch `molejo` (`480ed1f`)
      models both driven axes' GT2 belts as wraps from the design's own
      pulley geometry — X 404 teeth, Y 477 over a three-circle loop —
      with `anchor.at` bound to each carriage's driver expression;
      teeth travel with the carriage (sentinel-vertex assertions),
      21/21 green, document version 3 with two flexible nodes. API
      findings fed back: a public tangent-station helper would spare
      consumers re-deriving the external-tangent formula, and
      per-element `tessellation.path` over-samples short arcs (the
      19 mm end arc gets the 375 mm run's count).
- [ ] 8.3 Loom/filament: spline spec driven by three axis parameters
      validates the K^d claim — no sampling anywhere.
