## MODIFIED Requirements

### Requirement: A wrap evaluates to a closed planar loop

The Python evaluator SHALL evaluate a `wrap` to a closed planar loop,
taking each circle along the tangent its two senses call for and turning
each arc the way its own circle's sense says. The profile frame SHALL be
carried by the same rotation-minimizing transport throughout, so that
across a reverse bend the frame's local X swings from pointing away from
the circle to pointing at it.

#### Scenario: A reversed circle is ridden from the far side

- **WHEN** a wrap turns counterclockwise about a circle
- **THEN** every ring of that arc stands at the declared radius from its
  centre, on the opposite side from where a clockwise circle would be
  touched

#### Scenario: The loop still makes one net turn

- **WHEN** a loop contains a reverse bend
- **THEN** the signed turns of its arcs sum to exactly one revolution:
  the counterclockwise arc pays back what the extra clockwise arc on
  either side of it costs

### Requirement: Teeth displace the face the document names

The evaluator SHALL displace the profile vertices of the face `teeth`
names — toward the circles for the inner face, away from them for the
outer — and SHALL leave every other vertex where the untoothed profile
puts it.

#### Scenario: Outer teeth move only the outer face

- **WHEN** a wrap declares teeth on the outer face
- **THEN** the vertices at the profile's maximum local X differ from the
  untoothed belt's and every other vertex is identical to it

#### Scenario: Outward teeth meet the circle they are bent over

- **WHEN** a belt with outer teeth is bent backwards over a circle
- **THEN** on that arc the toothed face reaches from the circle's own
  radius to a whole tooth height inside it
