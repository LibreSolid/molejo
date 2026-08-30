## MODIFIED Requirements

### Requirement: A package version carries the spec version it implements

Both packages SHALL carry the spec version they implement and SHALL be
released together for it. Neither runtime SHALL be published against a
spec version the other has not caught up to.

#### Scenario: Spec version 2 is carried by 0.2.0

- **WHEN** either package declares its version
- **THEN** it is `0.2.0`, and both implement spec version 2 in full

#### Scenario: An older installation refuses what it cannot evaluate

- **WHEN** a `0.1.0` installation is given a document using a reverse
  bend or an outer tooth face
- **THEN** it rejects it as an unsupported spec version rather than
  evaluating part of it
