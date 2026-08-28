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

Each parity fixture is a spec plus parameter values plus the expected
vertex and face arrays; counts and ordering must match exactly,
coordinates within the tolerance each fixture declares.

Empty until spec v1 lands its first vertical slice.
