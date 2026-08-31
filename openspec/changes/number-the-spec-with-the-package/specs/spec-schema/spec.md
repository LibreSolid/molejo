## MODIFIED Requirements

### Requirement: A document declares the spec version it is written in

Every molejo document SHALL carry `molejo`, a string of the form
`MAJOR.MINOR` naming a spec version the implementation reads. A value
that is not a string, and a string outside the closed set of versions the
implementation reads, SHALL both be rejected naming the value found and
the versions that are read.

The spec versions this implementation reads are `"0.1"` and `"0.2"`,
oldest first. `"0.1"` is the spec molejo `0.1.0` shipped, which that
release spelled as the integer `1`; `"0.2"` is the reverse bend and the
outer tooth face.

#### Scenario: A document declaring a version that is read is accepted

- **WHEN** a document declares `"molejo": "0.1"` or `"molejo": "0.2"`
- **THEN** validation proceeds to the rest of the document

#### Scenario: A numeric version is rejected

- **WHEN** a document declares `"molejo": 1`, as molejo `0.1.0` wrote it
- **THEN** validation fails naming the value found and the spec version
  strings this implementation reads

#### Scenario: An unknown version is rejected

- **WHEN** a document declares a `MAJOR.MINOR` string this
  implementation does not read
- **THEN** validation fails naming the version found and the versions it
  reads

### Requirement: A document may not use vocabulary its version cannot express

A document SHALL NOT use vocabulary introduced after the spec version it
declares. Validation SHALL reject one that does, naming both versions and
the field that forced the higher one. Versions SHALL be ordered by their
position in the implementation's list of the versions it reads, which is
oldest first; no order is defined against a version it does not read,
because such a version is already refused.

#### Scenario: A 0.1 document using 0.2 vocabulary is rejected

- **WHEN** a document declares `"molejo": "0.1"` and carries a wrap
  circle with a `turn`, or teeth with a `face`
- **THEN** validation fails saying it declares spec version `'0.1'` but
  uses spec version `'0.2'` vocabulary, and names the field

### Requirement: An author writes the lowest version a document needs

Authoring SHALL write the lowest spec version that can express the
document, not the newest the implementation knows. `required_version` in
Python and `requiredVersion` in JavaScript SHALL return that version as
its `MAJOR.MINOR` string.

#### Scenario: A shape asking nothing of 0.2 authors a 0.1 document

- **WHEN** a shape uses no reverse bend and no outer tooth face
- **THEN** the document it authors declares `"molejo": "0.1"`

#### Scenario: A shape using 0.2 vocabulary authors a 0.2 document

- **WHEN** a shape uses a reverse bend or an outer tooth face
- **THEN** the document it authors declares `"molejo": "0.2"`
