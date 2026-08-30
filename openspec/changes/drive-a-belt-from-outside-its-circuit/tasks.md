## 1. The spec: two additions and a two-way version

- [x] 1.1 Red: a wrap circle declaring `turn` and a wrap's teeth
      declaring `face` are both rejected as unknown fields; an unknown
      value for either is not rejected at all, because neither field
      exists.
- [x] 1.2 Add `WRAP_TURNS` and `TOOTH_FACES` to the Python validator as
      closed literal vocabularies, and accept the two optional fields.
- [x] 1.3 Red: a document declaring `"molejo": 1` and carrying a `turn`
      validates, which it must not — the version integer would be a
      label rather than a promise.
- [x] 1.4 Implement `required_version` and the vocabulary gate in
      validation, naming the field that forces the higher version.
- [x] 1.5 Red: an authored shape with no version 2 vocabulary emits
      `"molejo": 2`, so every existing document would become unreadable
      by molejo 0.1.0.
- [x] 1.6 Author the lowest version a document needs, and assert the
      whole existing fixture set is byte-identical.
- [x] 1.7 Mirror all of it in `js/src/spec.js`, including
      `requiredVersion`, held to the Python messages by the shared
      rejection fixtures.
- [x] 1.8 Shared rejection fixtures: `unknown-wrap-turn.json`,
      `unknown-tooth-face.json`, `understated-version.json`; and
      `unsupported-version.json` moved off 2, which is now a version
      that is read.

## 2. The reverse bend

- [x] 2.1 Red (Python): a wrap with a counterclockwise circle draws the
      external tangent and turns the arc the wrong way, so the ring
      centres depart from the closed form and the loop's net turn is not
      one revolution.
- [x] 2.2 Generalize the closed form in `test_wrap.py` first — signed
      radii in the normal, contact angles rather than normal angles for
      an arc, the sense in the sampling — so the expectation is not
      derived from the evaluator.
- [x] 2.3 Implement signed radii in `_wrap_circles`, the sensed arc in
      `_wrap_elements`, and the sensed tangent in `_wrap_geometry`.
      Assert the reduction: every existing test stays green untouched.
- [x] 2.4 Red: two circles turning opposite ways and too close for an
      internal tangent are refused naming the *external* one.
- [x] 2.5 Name the missing tangent by the two senses.

## 3. The outward tooth face

- [x] 3.1 Red (Python): teeth declared on the outer face still displace
      the inner one.
- [x] 3.2 Replace `_inner_face` with `_toothed_face`, a signed per-vertex
      mask, and displace along it.
- [x] 3.3 Red: with outer teeth on a reverse bend, the toothed face does
      not reach into the circle the belt is bent over.
- [x] 3.4 Assert it does: the toothed face runs from the circle's own
      radius to a tooth height inside it, and the smooth face does not.

## 4. The exact evaluator

- [x] 4.1 Red: the B-rep of a reverse-bent belt is not closed, or its
      volume departs from the prism its traces enclose.
- [x] 4.2 Sense the arc edges' axis, the trace offsets and the angle
      advance in `_occt.py`; carry the teeth on the trace `face` names.
- [x] 4.3 Generalize the independent closed form in `test_brep.py` to
      signed radii and either tooth face, without borrowing a line of
      the evaluator.

## 5. Parity

- [x] 5.1 Build `reverse-bend-belt.json`: two bearings holding a belt
      against a reverse-bent pulley whose centre is a parameter, teeth
      on the outer face, six teeth circulating with a phase. Gate every
      number on the closed forms before writing the file — watertight,
      the whole vertex array predicted from the circles alone, the exact
      prism, and the B-rep within 1e-6 of the analytic volume.
- [x] 5.2 Choose the sampling against the tooth count, not for file
      size: an outward-toothed trace aliases at three rings a tooth and
      can come out larger than the solid it samples, which would break
      the suite's "the solid is the larger" invariant for the wrong
      reason. Twelve rings a tooth, as the other belt fixtures use.
- [x] 5.3 Add the closed form to `test_brep_parity.py` and the fixture
      to the manifest; both suites pick it up with no list of their own.
- [x] 5.4 Measure the faceting margin and declare a `brep.tolerance`
      inside the suite's own not-slack bound.

## 6. Release the spec version

- [x] 6.1 `SPEC_VERSION` 2 and `SPEC_VERSIONS` (1, 2) in both runtimes.
- [x] 6.2 Both packages to `0.2.0`; neither published — publishing is
      the maintainer's explicit decision and never a side effect.
- [x] 6.3 `docs/spec.md` (the wrap, the teeth, versioning both ways),
      `docs/python.md`, `docs/brep.md`, `docs/quickstart.md`,
      `README.md`, `fixtures/README.md`, `CHANGELOG.md`.

## 7. Validate in the consumer

- [x] 7.1 Draw the Metamaquina 2 Y belt with the pulley reverse-bent
      between its two rear bearings and its teeth outward, and record
      what it measures: 156° of wrap where the design had 22.5 mm of
      air, one groove of pulley per tooth of bed travel, every ring of
      every idler arc flush on the race, and the toothed face reaching a
      tooth height into the pulley's flank circle.
- [ ] 7.2 Publish. Not done, and not this change's to do: the packages
      carry 0.2.0 and `scripts/check-dist` uploads nothing.
