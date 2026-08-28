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
fixtures use the observed departure is about one Float32 ulp, some 4% of
the declared budget.

**Expectations come from the Python evaluator**, but only after that
evaluator has passed its own analytic assertions — watertightness, the
exact volume of the prism the tessellation describes, and the analytic
volume approached from below within the computed chord error. Numbers
copied from an unvalidated implementation would pin a bug in two
languages instead of catching one.

**`manifest.json` names every parity fixture**, and both suites assert it
agrees with the directory:

```json
{ "parity": ["cylinder.json", "oblique-line.json", "quarter-bend.json",
             "spring.json"] }
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
