## MODIFIED Requirements

### Requirement: A wrap builds exactly as lines and arcs

The B-rep evaluator SHALL build a reverse bend from the same exact lines
and arcs as any other wrap, with an arc's circle carrying the axis its
sense calls for, and SHALL offset a trace along the profile's local X
signed by that sense. A toothed belt SHALL carry its teeth on the trace
the document's `face` names, and the other trace SHALL remain lines and
arcs.

#### Scenario: A reverse-bent belt is a closed solid

- **WHEN** a belt with a reverse bend and outer teeth is evaluated to a
  B-rep
- **THEN** the result is a closed solid whose volume matches the closed
  form for the prism its two traces enclose

#### Scenario: The solid is still the larger of the two

- **WHEN** the reverse-bend fixture's solid is compared with the faceted
  mesh the fixture pins
- **THEN** the solid's volume and area exceed the mesh's, and the solid
  is nearer the closed form than the mesh is
