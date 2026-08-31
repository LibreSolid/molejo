## Why

The spec version and the package version count at different speeds, and
the spec version is the faster of the two. molejo `0.1.0` carried spec
version `1`; molejo `0.2.0`, prepared but not yet released, carries spec
version `2`. Two releases in, the spec is already twice as old as the
software, and by `0.9.0` it could plausibly be on version 9 — a number
that means nothing to anyone and matches nothing they installed.

There is no reason for two counters. Every spec version so far has
arrived in exactly one release, and every release that changed the spec
bumped its own minor at the same time. The second counter carries no
information the first does not, and costs a reader the work of holding a
mapping in their head: *which molejo do I need for a v2 document?*

The moment to fix it is now. `0.2.0` is prepared but untagged and
unpublished, so only `0.1.0` is out in the world — unannounced, with one
known user, who is the author. A later fix would be a real migration; this
one is a rename.

## What Changes

The spec version becomes the `MAJOR.MINOR` of the release that
introduced it, written as a JSON string:

- **spec-schema**: `"molejo"` SHALL be a string of the form
  `MAJOR.MINOR`. What the previous change called spec version `2` is spec
  version `"0.2"`, and what `0.1.0` shipped as spec version `1` is spec
  version `"0.1"`. The two-way version gate, `required_version`, and the
  ordering it needs are unchanged in behaviour; only the token changes.
  The integer form is rejected — not aliased — naming the versions that
  are read, so a `0.1.0`-era document fails loudly rather than quietly.
- **distribution**: both packages stay at `0.2.0`, now carrying spec
  version `"0.2"`. Until `1.0`, a release that changes the spec takes its
  own `MAJOR.MINOR` as the new spec version; a release that does not keeps
  the spec version it inherited. So a spec version is always a release
  that existed, but not every release mints one.
- **parity**: every fixture's `molejo` field becomes a string, and one
  new rejection fixture pins the refusal of a numeric version.

Nothing about the geometry, the vocabulary, or the evaluators changes. A
`0.1.0` document is still a valid document under the name `"0.1"`; only
the name it must write for itself is different.

## Capabilities

### New Capabilities

None. This changes how three existing capabilities name a thing they
already have.

### Modified Capabilities

`spec-schema`, `distribution`, `parity`.

## Impact

- `python/molejo/spec.py` — `SPEC_VERSIONS`, the two rejection branches,
  `_required_version`, and the ordering comparison.
- `js/src/spec.js` — the twin of all of it.
- Every fixture under `fixtures/` and `fixtures/invalid/`: `"molejo": 1`
  becomes `"molejo": "0.1"` and `"molejo": 2` becomes `"molejo": "0.2"`.
- `fixtures/invalid/unsupported-version.json` and
  `understated-version.json` — their spec and their `must_mention`; and
  a new `fixtures/invalid/numeric-version.json`.
- `python/tests/`, `js/test/` — every asserted document and message.
- `README.md`, `js/README.md`, `CHANGELOG.md`, `fixtures/README.md`,
  `docs/spec.md`, `docs/quickstart.md`, `docs/javascript.md`,
  `docs/installation.md`.

## Out of scope

- Accepting the integer form as an alias for the string. It would keep a
  dead vocabulary alive forever to spare one known user one error
  message, and that user asked for the rename.
- Republishing or yanking `0.1.0`. It is what it is: a release that read
  and wrote `"molejo": 1`. The changelog says so, under the name the spec
  now goes by.
- What the rule becomes at `1.0`, when the spec version stops tracking
  the package version. The string form leaves room for whatever is
  decided then; deciding it now would be inventing a requirement.
