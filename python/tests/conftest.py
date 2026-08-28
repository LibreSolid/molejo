# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Shared test helpers: the repository's fixture tree and the canonical
spring document the README advertises."""

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


def invalid_documents():
    """Every shared invalid-document fixture, sorted by file name."""
    directory = FIXTURES / "invalid"
    files = sorted(directory.glob("*.json"))
    assert files, f"no invalid-document fixtures found in {directory}"
    return [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in files]


@pytest.fixture
def spring_document():
    return json.loads(json.dumps(SPRING_DOCUMENT))
