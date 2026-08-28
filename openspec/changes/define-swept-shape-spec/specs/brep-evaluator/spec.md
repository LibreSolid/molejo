## ADDED Requirements

### Requirement: Spec plus values to an exact B-rep solid

The Python package SHALL provide an OCCT-backed evaluator, installed
as the `brep` extra, that evaluates a valid spec plus a
`{parameter: number}` mapping to a single closed B-rep solid. Path
curves SHALL be constructed exactly — lines and arcs as analytic
edges, a helix as a curve on a cylindrical surface, splines as
B-spline curves — never sampled from a mesh evaluation.

#### Scenario: A spring instant becomes an exact solid

- **WHEN** the valve-spring spec is evaluated under a binding by the
  B-rep evaluator
- **THEN** the result is one closed solid swept along the exact helix,
  usable for boolean, clearance, and volume assertions by a consumer's
  exact-shape testing machinery

### Requirement: Surface exactness is honest and maximal

Sweeps along `line` and `arc` primitives (including `wrap` chains)
SHALL produce exact analytic surfaces (planes, cylinders, toroidal
patches). Sweeps along `helix` and `spline` paths SHALL produce
B-spline surfaces approximated within a tolerance the evaluator
declares on the result. The evaluator SHALL NOT degrade an
analytically representable sweep to an approximated surface.

#### Scenario: A belt loop is fully analytic

- **WHEN** a circle-profile `wrap` spec is evaluated
- **THEN** every lateral face of the solid is a cylindrical or
  toroidal patch and the declared approximation tolerance is zero

### Requirement: Property parity with the mesh evaluators

For every parity fixture, the B-rep evaluation of the fixture's spec
and bindings SHALL agree with the expected mesh on analytic properties
— volume and surface area within the fixture's declared tolerance.
B-rep output has no vertex contract; property agreement is its parity.

#### Scenario: Fixture volumes agree across representations

- **WHEN** the parity suite runs with the `brep` extra installed
- **THEN** each fixture's B-rep volume matches its expected-mesh
  volume within the fixture tolerance, and a departure fails naming
  the fixture

### Requirement: Optional dependency, loud boundary

The mesh evaluator and STL export SHALL work without the `brep` extra
installed. Using the B-rep evaluator without it SHALL raise an error
naming the extra. Evaluation failures (unknown primitive, dangling
parameter) SHALL match the mesh evaluator's loud-failure contract.

#### Scenario: The extra is absent

- **WHEN** the B-rep evaluator is invoked in an environment without
  the OCCT dependency
- **THEN** it raises naming the `brep` extra, and mesh evaluation in
  the same environment is unaffected
