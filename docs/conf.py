# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Sphinx configuration for molejo.readthedocs.io."""

project = "molejo"
author = "Luis Henrique Cassis Fagundes"
copyright = "2026, Luis Henrique Cassis Fagundes"

try:
    from importlib.metadata import version as _distribution_version

    release = _distribution_version("molejo")
except Exception:
    release = "0.1.0"
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
}

# The docstrings document arguments in prose, so signatures alone carry
# the shape of the API; members keep the source order they were written in.
autodoc_member_order = "bysource"

html_theme = "furo"
html_title = f"molejo {release}"

exclude_patterns = ["_build"]
