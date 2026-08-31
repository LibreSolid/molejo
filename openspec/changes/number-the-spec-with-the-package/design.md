# Design

## A string, not a number

`MAJOR.MINOR` cannot be a JSON number. `0.10` and `0.1` are the same
float, so the tenth minor spec version would collide with the first, and
a validator would have no way to tell a reader which one it had. Nor can
it be two fields; a version that arrives in two slots is a version every
consumer has to reassemble before it can compare anything.

So `"molejo"` is a string: `"0.1"`, `"0.2"`. It reads the way the release
it names reads, it survives the tenth minor, and it stays a single
scalar.

## Ordering without parsing

The version gate needs one comparison — *is the version this document
declares lower than the version its vocabulary needs* — and both operands
are drawn from a closed, ordered list the implementation ships. So the
comparison is by position in `SPEC_VERSIONS`, taken after the declared
version is known to be in it. No parsing, no collation rules, no
opinion about what a version string means beyond the order the
implementation was written with.

That deliberately gives up the ability to compare against a version the
implementation has never heard of. It does not need to: an unknown
version is already refused, one branch earlier, as one it cannot read.

## The integer form is refused, not aliased

A `0.1.0` document declares `"molejo": 1`, and every one of them is a
document the new validator would otherwise be able to read. Aliasing `1`
to `"0.1"` would cost four lines and would keep them working.

It is still the wrong trade. The alias would be permanent — nothing ever
justifies removing it later that does not justify not adding it now — and
it would mean two spellings of every version forever, which is the exact
confusion the rename exists to end. Against that, the cost is one error
message to one known user on documents they can fix with a text editor.

So the numeric form falls into the ordinary "must be a spec version
string" branch, which names the versions that are read. A reader who sees
it gets `'0.1'` and `'0.2'` in the message, which is the answer to the
question they are about to ask.

## The published 0.1.0 is left alone

molejo `0.1.0` is on PyPI and npm. It writes `"molejo": 1` and reads
nothing else, and no edit here changes that. What changes is the name the
project uses for the spec that release implements: it is spec `0.1`, and
the changelog entry says so while recording that the shipped packages
spelled it `1`.

The alternative — rewriting the `0.1.0` entry as though it had always
been `"0.1"` — would make the changelog disagree with an artifact anyone
can download. A changelog that lies about a published release is worse
than one that records a rename.
