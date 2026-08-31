## MODIFIED Requirements

### Requirement: A package version carries the spec version it implements

Both packages SHALL carry the spec version they implement and SHALL be
released together for it. Neither runtime SHALL be published against a
spec version the other has not caught up to.

Before `1.0`, a spec version SHALL be the `MAJOR.MINOR` of the release
that introduced it. A release that changes the spec SHALL mint a spec
version equal to its own `MAJOR.MINOR`; a release that does not SHALL
keep the spec version it inherited. So every spec version names a release
that existed, and not every release mints one.

#### Scenario: Spec version 0.2 is carried by 0.2.0

- **WHEN** either package declares its version
- **THEN** it is `0.2.0`, and both implement spec version `"0.2"` in full

#### Scenario: A release that leaves the spec alone mints no version

- **WHEN** a release changes neither the document vocabulary nor its
  rules
- **THEN** it carries the spec version its predecessor carried

#### Scenario: An older installation refuses what it cannot evaluate

- **WHEN** a `0.1.0` installation is given a document using a reverse
  bend or an outer tooth face
- **THEN** it rejects it as an unsupported spec version rather than
  evaluating part of it
