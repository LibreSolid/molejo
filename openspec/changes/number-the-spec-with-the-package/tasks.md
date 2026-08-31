## 1. The version token becomes a string

- [x] 1.1 Red (Python): a document declaring `"molejo": "0.1"` is
      rejected as not one of the integers, and one declaring `1` is
      accepted — the whole of the old spelling, still in force.
- [x] 1.2 `SPEC_VERSIONS = ("0.1", "0.2")`; the version branches accept
      a `MAJOR.MINOR` string from that set, reject anything else naming
      the value and the versions read, and reject a numeric version
      through the same branch.
- [x] 1.3 Order by position in `SPEC_VERSIONS` for the vocabulary gate,
      and return the version string from `_required_version` /
      `required_version`.
- [x] 1.4 Mirror all of it in `js/src/spec.js`, message for message.

## 2. The fixtures

- [x] 2.1 Every fixture under `fixtures/` and `fixtures/invalid/`:
      `"molejo": 1` becomes `"0.1"`, `"molejo": 2` becomes `"0.2"`.
- [x] 2.2 `unsupported-version.json` moves to a `MAJOR.MINOR` string the
      implementation does not read; `understated-version.json` updates
      its `must_mention` to the quoted version strings.
- [x] 2.3 New `fixtures/invalid/numeric-version.json`: `"molejo": 1`,
      the form molejo `0.1.0` wrote, now refused.
- [x] 2.4 Both suites green against the shared fixtures, with the
      authored documents byte-identical to the committed ones but for
      the version string.

## 3. The tests

- [x] 3.1 Python: every asserted document and message in
      `python/tests/`.
- [x] 3.2 JavaScript: the same in `js/test/`.
- [x] 3.3 Both suites green; the B-rep suite green where OCCT is
      installed.

## 4. The record

- [x] 4.1 `docs/spec.md` — the version field, its table row, the
      versioning section, and the two `**Spec version 2.**` markers.
- [x] 4.2 `docs/quickstart.md`, `docs/javascript.md`,
      `docs/installation.md`, `fixtures/README.md`.
- [x] 4.3 `README.md` and `js/README.md`.
- [x] 4.4 `CHANGELOG.md`: the `0.2.0` entry states the renaming and the
      refusal of the numeric form; the `0.1.0` entry names its spec
      `0.1` while recording that the published packages spelled it `1`.
- [x] 4.5 Leave this change beside the other two in
      `openspec/changes/`. `openspec archive` needs baseline specs under
      `openspec/specs/` to modify, and this repository has never synced
      any — the changes themselves are the record, and both earlier ones
      are unarchived for the same reason.
