## 1. Spec schema and validation

- [ ] 1.1 Red: a schema document with an unknown primitive, a dangling
      parameter reference, an open profile, or missing tessellation
      counts is rejected with an error naming the offending slot.
- [ ] 1.2 Implement the schema model and validator in Python
      (`molejo.spec`): version tag, profile, path chain, parameter
      references, declared tessellation counts.
- [ ] 1.3 Implement schema parsing and the same validations in JS;
      shared invalid-document fixtures under `fixtures/invalid/` run
      red on both sides first.
- [ ] 1.4 Red: Python authoring constructors (`Shape`, profiles, path
      primitives, `P`) serialize to exactly the canonical JSON of the
      equivalent hand-written spec; a parameter reference used in
      arithmetic raises.
- [ ] 1.5 Implement the authoring layer over the schema model.

## 2. First vertical slice: circle profile, line path

- [ ] 2.1 Red (Python): a cylinder spec (circle profile swept along one
      line) evaluates to a watertight mesh with exactly the declared
      vertex count, capped ends, and the analytically correct volume
      within tolerance.
- [ ] 2.2 Implement profile evaluation, frame transport along a line,
      capping, and mesh assembly in Python.
- [ ] 2.3 Red (Python): the same spec with the line length as
      `{"param": "length"}` evaluates differently under two parameter
      bindings and identically under repeated identical bindings.
- [ ] 2.4 Implement parameter resolution.
- [ ] 2.5 First parity fixture: the cylinder spec, two parameter
      bindings, expected arrays; JS side red, then implement the JS
      twin (profile, line, caps) until parity passes.
- [ ] 2.6 STL export from the Python evaluation (binary STL bytes),
      asserted watertight by an independent reader.

## 3. Arc and helix

- [ ] 3.1 Red: arc path fixture (quarter-bend tube) — counts, ordering,
      endpoint frames continuous with adjoining line segments.
- [ ] 3.2 Implement `arc` in Python, then JS, to fixture parity.
- [ ] 3.3 Red: helix fixture — a spring at two pitches bound via
      `{"param": "pitch"}`; wire cross-section stays circular (no axial
      shear of the profile), coil count fixed.
- [ ] 3.4 Implement `helix` in Python, then JS, to fixture parity.

## 4. Wrap and spline

- [ ] 4.1 Settle the `wrap` signature against the belt validation case
      (ordered circles, side flags, phase, open-span anchor); record
      the decision in design.md before implementing.
- [ ] 4.2 Red: wrap fixture — closed loop around three circles;
      tangency continuity; phase parameter circulates the profile
      pattern without changing counts.
- [ ] 4.3 Implement `wrap` in Python, then JS, to fixture parity.
- [ ] 4.4 Settle the spline flavor against the loom validation case;
      record the decision in design.md.
- [ ] 4.5 Red: spline fixture — a loom run whose end point and tangents
      are parameter references in three names (x, y, z); evaluation
      cost measured independent of parameter count.
- [ ] 4.6 Implement `spline` in Python, then JS, to fixture parity.

## 5. Parity harness

- [ ] 5.1 Python suite runs every fixture in `fixtures/`; JS suite runs
      the same files; a fixture present on one side and missing from
      the other fails that side's suite.
- [ ] 5.2 Fixture format documents counts-and-ordering exactness and
      per-fixture coordinate tolerance; one deliberately perturbed
      expectation proves both suites actually compare.

## 6. Distribution

- [ ] 6.1 `python -m build` produces an installable wheel from
      `python/`; a clean-venv install imports `molejo` and evaluates
      the cylinder fixture.
- [ ] 6.2 `npm pack` from `js/` produces an installable package; a
      scratch consumer imports it and evaluates the cylinder fixture.
- [ ] 6.3 Version discipline recorded in README: package versions carry
      the spec version they implement; publishing itself waits for the
      pilot's explicit go.

## 7. Validation cases (consumer-side, evidence recorded here)

- [ ] 7.1 Valve spring: helix spec driven by one lift parameter renders
      and animates in the consuming framework's viewer.
- [ ] 7.2 Belt: wrap spec with circulating phase and carriage-anchored
      span validates against the belt case.
- [ ] 7.3 Loom/filament: spline spec driven by three axis parameters
      validates the K^d claim — no sampling anywhere.
