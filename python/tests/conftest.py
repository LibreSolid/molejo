# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Shared test helpers: the repository's fixture tree and the canonical
spring document the README advertises.

Fixture discovery is deliberately the same on both sides: the manifest
names every parity fixture, both suites assert that the manifest and the
directory agree, and both run everything the manifest names. A fixture
added for one runtime cannot be quietly skipped by the other, because
neither suite has a list of its own to fall behind."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

#: The hand-written canonical document for the README's valve spring.
SPRING_DOCUMENT = {
    "molejo": 1,
    "profile": {"type": "circle", "radius": 2.0},
    "path": [
        {
            "type": "helix",
            "radius": 14.0,
            "turns": 6.5,
            "height": {"param": "height"},
        }
    ],
    "loop": False,
    "tessellation": {"path": 240, "profile": 16},
}


#: The index of parity fixtures, and the one file in `fixtures/` that is
#: not itself a fixture.
MANIFEST = "manifest.json"


def parity_manifest():
    """The fixture file names the manifest says both suites must run."""
    return json.loads((FIXTURES / MANIFEST).read_text(encoding="utf-8"))["parity"]


def parity_files():
    """The parity fixture files actually present in `fixtures/`."""
    return sorted(
        path.name for path in FIXTURES.glob("*.json") if path.name != MANIFEST
    )


def parity_fixture(filename):
    return json.loads((FIXTURES / filename).read_text(encoding="utf-8"))


def invalid_documents():
    """Every shared invalid-document fixture, sorted by file name."""
    directory = FIXTURES / "invalid"
    files = sorted(directory.glob("*.json"))
    assert files, f"no invalid-document fixtures found in {directory}"
    return [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in files]


@pytest.fixture
def spring_document():
    return json.loads(json.dumps(SPRING_DOCUMENT))
