## MODIFIED Requirements

### Requirement: The JavaScript evaluator is the Python one's twin

The JavaScript evaluator SHALL evaluate a reverse bend and either tooth
face identically to the Python evaluator — same vertex count, same
ordering, coordinates within the fixture's declared tolerance — and
SHALL emit the same refusals, word for word.

#### Scenario: A reverse-bend belt agrees across runtimes

- **WHEN** both runtimes evaluate the reverse-bend parity fixture at
  each of its bindings
- **THEN** counts and face arrays match exactly and coordinates match
  within tolerance

#### Scenario: The same refusals, word for word

- **WHEN** a document declares an unknown `turn`, an unknown tooth
  `face`, or a version below the one its vocabulary needs
- **THEN** both runtimes reject it with the message the shared rejection
  fixture requires

### Requirement: The version vocabulary gate is enforced in the browser too

The JavaScript validator SHALL read spec versions 1 and 2 and SHALL
reject a document whose declared version cannot express its own
vocabulary. It SHALL expose the lowest version a document needs, so a
consumer that emits documents of its own can declare no more than it
needs.

#### Scenario: A browser consumer asks what a document needs

- **WHEN** `requiredVersion` is given a document with no version 2
  vocabulary
- **THEN** it answers 1
