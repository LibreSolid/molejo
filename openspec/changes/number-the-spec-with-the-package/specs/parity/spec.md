## MODIFIED Requirements

### Requirement: Shared rejection fixtures pin both validators to the same messages

The shared fixtures under `fixtures/invalid/` SHALL hold both validators
to the same refusals, each fixture naming the substrings its message must
mention. The set SHALL include the two ways a spec version can be wrong
in its own right — a version that is not a `MAJOR.MINOR` string, and a
`MAJOR.MINOR` string the implementation does not read — as well as a
document that understates its own version.

#### Scenario: A numeric spec version is refused identically by both

- **WHEN** either validator is given `fixtures/invalid/numeric-version.json`
- **THEN** it rejects the document naming `molejo`, that a spec version
  string is required, and the value it found

### Requirement: Every parity fixture is a valid document of a version both evaluators read

Each fixture under `fixtures/` SHALL declare its spec version as a
`MAJOR.MINOR` string, and SHALL declare the lowest version that can
express it.

#### Scenario: The version 0.1 fixtures are unchanged but for their version string

- **WHEN** a fixture uses no reverse bend and no outer tooth face
- **THEN** it declares `"molejo": "0.1"` and evaluates, in both
  runtimes, to exactly the vertices it did before
