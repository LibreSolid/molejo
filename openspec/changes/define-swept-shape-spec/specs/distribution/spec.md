## ADDED Requirements

### Requirement: One repository, two packages, one spec version

The repository SHALL build an installable Python package `molejo` from
`python/` and an installable npm package `molejo` from `js/`. Each
released package version SHALL declare which spec version it
implements, and the two packages SHALL be released together for a given
spec version. Publishing to either registry happens only on the
maintainer's explicit decision, never as an implementation side effect.

#### Scenario: A clean install evaluates

- **WHEN** the built wheel is installed into a clean environment
- **THEN** `import molejo` succeeds and evaluates the cylinder parity
  fixture

#### Scenario: The npm package installs

- **WHEN** the packed npm tarball is installed into a scratch project
- **THEN** importing `molejo` succeeds and evaluates the cylinder
  parity fixture
