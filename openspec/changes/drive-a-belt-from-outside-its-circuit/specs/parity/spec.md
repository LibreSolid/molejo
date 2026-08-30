## ADDED Requirements

### Requirement: A reverse bend and an outward tooth face are pinned by a fixture

`fixtures/` SHALL carry a parity fixture exercising a wrap with a
reverse-bent circle and teeth on the outer face together, with the
reverse-bent circle's centre bound to a parameter so that both internal
tangents and the loop length move between bindings. Both suites SHALL
run it, and the B-rep suite SHALL check it against a closed form written
independently of either evaluator.

#### Scenario: An evaluator that took the external tangent

- **WHEN** an evaluator wraps the reverse-bent circle the ordinary way,
  turns its arc the ordinary way, or displaces the inner face
- **THEN** the fixture fails on the first departing vertex of the first
  case

### Requirement: The new refusals are pinned by rejection fixtures

`fixtures/invalid/` SHALL carry a document with an unknown wrap `turn`,
one with an unknown tooth `face`, and one that declares a spec version
below the one its own vocabulary needs. Both suites SHALL reject each,
naming the substrings the fixture requires.

#### Scenario: A one-sided refusal

- **WHEN** one runtime rejects an unknown `turn` and the other does not
- **THEN** that runtime's suite fails, naming the fixture
