## ADDED Requirements

### Requirement: A wrap circle declares which way the belt turns about it

Each circle of a `wrap` SHALL accept an optional `turn`, either
`"clockwise"` (the default) for a circle inside the loop or
`"counterclockwise"` for one the belt is bent backwards over. It SHALL
be a literal from that closed vocabulary and never a parameter
reference: a circle's sense decides which tangents the loop takes and so
how many elements it has, and an element count may not follow a value.

#### Scenario: A circle with no turn is wrapped the ordinary way

- **WHEN** a wrap circle declares no `turn`
- **THEN** the belt wraps it clockwise, exactly as spec version 1 did

#### Scenario: An unknown turn is rejected

- **WHEN** a wrap circle declares a `turn` outside the vocabulary
- **THEN** validation fails naming the circle, the value, and the two
  turns it expected

### Requirement: A tooth pattern declares which face it stands on

A wrap's `teeth` SHALL accept an optional `face`, either `"inner"` (the
default) for the profile vertices at the minimum local X, displaced
toward the circles, or `"outer"` for the vertices at the maximum,
displaced away from them. It SHALL be a literal from that closed
vocabulary.

#### Scenario: Teeth with no face are inner teeth

- **WHEN** a wrap's teeth declare no `face`
- **THEN** the inner face is displaced, exactly as spec version 1 did,
  and the document is a spec version 1 document

#### Scenario: An unknown tooth face is rejected

- **WHEN** a wrap's teeth declare a `face` outside the vocabulary
- **THEN** validation fails naming the field, the value, and the two
  faces it expected

### Requirement: A document may not use vocabulary its version cannot express

Validation SHALL reject a document whose declared spec version is lower
than the lowest version its own vocabulary requires, naming the field
that requires the higher one. A version integer is a promise about which
implementations can read a document; a document that understates it
would reach an older implementation as a malformed field rather than as
one written for a newer molejo.

#### Scenario: A version 1 document using a reverse bend

- **WHEN** a document declares `"molejo": 1` and one of its wrap circles
  declares a `turn`
- **THEN** validation fails naming that circle's `turn` and the version
  it needs

### Requirement: A document declares the lowest version it needs

An implementation that authors documents SHALL write the lowest spec
version that can express the document, not the newest version it reads.
A shape that uses no vocabulary beyond version 1 SHALL emit a version 1
document, unchanged from what it emitted before version 2 existed.

#### Scenario: An existing shape authors an unchanged document

- **WHEN** a shape using only version 1 vocabulary is authored
- **THEN** its document declares `"molejo": 1` and is byte-identical to
  the document the same shape authored under a version 1 implementation

#### Scenario: A reverse-bent shape marks itself

- **WHEN** a shape whose wrap turns counterclockwise about a circle is
  authored
- **THEN** its document declares `"molejo": 2`

## MODIFIED Requirements

### Requirement: Spec version

A document SHALL carry an integer spec version. This implementation
SHALL read versions 1 and 2, and SHALL reject any other value naming the
version it found and the versions it reads. Version 2 SHALL only add
vocabulary: every version 1 document remains valid and evaluates to
identical vertices.

#### Scenario: A version 1 document is read unchanged

- **WHEN** a version 1 document is evaluated
- **THEN** it produces the vertices it always produced

#### Scenario: An unknown version is rejected

- **WHEN** a document declares a version outside those read
- **THEN** validation fails naming the version found and the versions
  read

### Requirement: The wrap vocabulary

A `wrap` SHALL be a closed planar loop around at least two ordered
circles, running clockwise seen from +Z, with each circle taken along
the tangent its two senses call for: external where consecutive circles
turn the same way, internal where they differ. Consecutive circles too
close to admit that tangent SHALL be rejected at evaluation, naming
which kind of tangent is missing.

#### Scenario: A reverse bend takes the internal tangent

- **WHEN** a wrap runs from a clockwise circle to a counterclockwise one
- **THEN** the span between them crosses between their centres, touching
  the first along the shared normal and the second against it

#### Scenario: Two circles too close for an internal tangent

- **WHEN** two consecutive circles turn opposite ways and stand closer
  than the sum of their radii
- **THEN** evaluation fails naming the pair and the internal tangent
