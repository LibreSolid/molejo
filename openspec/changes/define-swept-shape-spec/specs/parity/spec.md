## ADDED Requirements

### Requirement: Shared fixtures pin the evaluators to each other

Parity fixtures SHALL live in `fixtures/` as data files each carrying a
spec, one or more parameter bindings, expected vertex and face arrays,
and a coordinate tolerance. Both evaluators' test suites SHALL run
every fixture: vertex counts and ordering match exactly; coordinates
match within the fixture's tolerance.

#### Scenario: A drifted implementation fails both ways

- **WHEN** one evaluator's output for a fixture departs from the
  expected arrays beyond tolerance
- **THEN** that suite fails naming the fixture and the first departing
  vertex

### Requirement: No primitive without a fixture

A path primitive or profile SHALL be considered implemented only when
at least one fixture exercising it passes on both evaluators. A fixture
present for one suite and absent from the other SHALL fail the suite
that lacks it.

#### Scenario: A one-sided primitive

- **WHEN** a primitive is implemented in Python with a fixture, and the
  JS suite runs without that fixture wired
- **THEN** the JS suite fails, naming the missing fixture
