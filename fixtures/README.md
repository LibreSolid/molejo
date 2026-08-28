# Shared fixtures

Fixtures both the Python and the JavaScript suites run, so the two
implementations cannot drift from each other.

## `invalid/` — rejection fixtures

One document per file that is *not* a valid molejo spec, with the
substrings the rejection must name:

```json
{
  "name": "unknown path primitive",
  "spec": { "molejo": 1, "…": "…" },
  "must_mention": ["path[1]", "unknown path primitive", "squiggle"]
}
```

Both suites iterate every file in this directory, assert that validation
fails, and assert the error message contains every `must_mention`
substring. The substrings are chosen to be stable across languages —
element locations (`path[1].to[2]`, `tessellation.profile`), vocabulary
names, and field names — never a runtime's type names or number
formatting. In practice the two validators emit byte-identical messages;
`must_mention` is the contract, and identity is the habit.

A fixture present here and unhandled by one side fails that side's suite,
so a new validation rule is added once as a fixture and paid for twice.

## Parity fixtures

One `*.json` file per fixture at the top of this directory — everything
except `manifest.json`, which is the index rather than a fixture:

```json
{
  "name": "cylinder: a circle profile swept along one line",
  "description": "what this fixture exists to catch",
  "spec": { "molejo": 1, "…": "…" },
  "tolerance": { "python": 1e-12, "js": 1e-6 },
  "brep": { "tolerance": 0.062 },
  "faces": [[0, 1, 13], "…"],
  "cases": [
    { "name": "short", "values": { "length": 12.0 },
      "vertices": [[5.0, 0.0, 0.0], "…"] }
  ]
}
```

**Counts and ordering are exact.** Vertex *i* is the same material point
in both runtimes and under every binding, or fixed tessellation buys
nothing; a departing count, a departing face, or a departing vertex
fails the suite naming the fixture, the case, and the first element that
drifted.

**The topology is stored once, not per case.** `faces` sits beside
`spec` because the claim under test is that the counts never follow a
parameter — the format should not be able to express its violation. For
the same reason a fixture carries at least two bindings: one cannot show
that the coordinates move while the numbering holds still.

**Tolerance is declared per runtime**, and a coordinate passes when
`|actual - expected| <= tolerance * (1 + |expected|)`, so the same number
covers coordinates near zero and far from it. Python compares float64
against the stored JSON, which round-trips exactly, and its tolerance is
headroom for a platform's libm rather than for its own arithmetic.
JavaScript writes `Float32Array` positions, so its tolerance must absorb
single precision and is always the looser of the two; at the sizes these
fixtures use the observed departure is about one Float32 ulp, some 4% to
6% of the declared budget. That holds for the curved and chained paths too,
whose frames are composed rotation by rotation: the composition tracks
its float64 twin closely enough that single precision is still the whole
of the difference.

**`brep` is a property tolerance, and it is not a coordinate tolerance.**
The B-rep evaluator produces a solid with no vertex contract — no rings to
number, no faces to order — so its parity is the volume and the area of
that solid against the volume and the area of the arrays stored here. The
two are not meant to agree closely: a faceted mesh is inscribed in the
smooth solid it samples, so a circle profile of *M* vertices encloses
`(M/2π)·sin(2π/M)` of its circle — 4.5% short at *M* = 12 and 17% at
*M* = 6 — and the path facets cut in from below as well. `brep.tolerance`
is therefore a *relative* bound on both properties, per fixture, measured
from that margin and given about 30% of headroom; the suite fails a
fixture whose declared tolerance is more than twice its measured one, so
headroom cannot quietly become licence. The gap is one-sided and asserted
so: the exact solid is always the larger. And the same solid is checked
against an independent closed form at 1e-6 — five orders tighter than any
of these numbers — which is what makes the loose bound mean "nearer truth
than the facets" rather than "close enough".

Every parity fixture must declare one, and every parity fixture must have
a closed form written out in the B-rep parity suite, or that suite fails
naming the fixture. `tolerance` stays exactly the two runtimes' coordinate
budgets, so the JavaScript suite never reads `brep` and never has to.

**Expectations come from the Python evaluator**, but only after that
evaluator has passed its own analytic assertions — watertightness, the
exact volume of the prism the tessellation describes, and the analytic
volume approached from below within the computed chord error. Numbers
copied from an unvalidated implementation would pin a bug in two
languages instead of catching one. The belt fixtures are gated the same
way and rather harder: the whole vertex array predicted from the
circles alone, the closed-form loop length, tangency at every contact,
the tooth crest and root radii, one full clockwise turn, and the exact
prism the belt's inner and outer faces enclose — which a planar wrap of
rectangular section admits in closed form, teeth included. The loom
fixtures are gated on the Hermite chain reproduced independently: both
declared ends reached bit for bit through the cap centres, every ring
centre on the closed-form curve, every ring across the closed-form
tangent with the tube's cross-section still circular, the ring at each
interior point across the tangent the two spans share, and the mitred
tube the sampling describes.

**`manifest.json` names every parity fixture**, and both suites assert it
agrees with the directory:

```json
{ "parity": ["carriage-belt.json", "cylinder.json", "filament-loom.json",
             "loom-lead-in.json", "oblique-line.json", "quarter-bend.json",
             "spring.json", "three-pulley-belt.json"] }
```

Neither suite keeps a list of its own, so a fixture added for one runtime
cannot be quietly skipped by the other; it can only be missing from the
manifest, and then both suites fail.

**The comparators are themselves under test.** Each suite feeds every
fixture through its own comparison code five times over, deliberately
perturbed — a moved vertex, a rewired face, a dropped vertex, a dropped
face, and a perturbation placed just inside tolerance — and demands the
first four fail and the last pass. A comparator that compares nothing
and a comparator that rejects everything are both caught.
