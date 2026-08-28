# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The shared invalid-document fixtures, run against the Python validator.

The JavaScript suite runs the same files and asserts the same substrings,
so the two implementations cannot drift in what they reject or in how they
name the offending element.
"""

import pytest

from molejo.spec import SpecError, validate

from conftest import invalid_documents

CASES = invalid_documents()


@pytest.mark.parametrize(
    "filename,fixture", CASES, ids=[name for name, _ in CASES]
)
def test_invalid_fixture_is_rejected_naming_the_offending_element(filename, fixture):
    with pytest.raises(SpecError) as caught:
        validate(fixture["spec"])

    message = str(caught.value)
    for substring in fixture["must_mention"]:
        assert substring in message, (
            f"{filename}: error message {message!r} does not mention {substring!r}"
        )


def test_every_fixture_declares_a_name_and_expectations():
    for filename, fixture in CASES:
        assert fixture["name"], f"{filename} has no name"
        assert fixture["must_mention"], f"{filename} asserts nothing about the message"
