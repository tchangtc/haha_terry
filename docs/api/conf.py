"""Sphinx configuration for Terry API documentation.

Build with:
    pip install sphinx furo
    cd docs/api && sphinx-build -b html . _build/html
"""

from __future__ import annotations

import os
import sys

# Add project root to path for autodoc
sys.path.insert(0, os.path.abspath("../.."))

# ── Project metadata ──────────────────────────────────────────────────
project = "Terry"
version = "0.9.0"
release = "0.9.0"
author = "Terry Contributors"
copyright = "2025–2026, Terry Contributors"

# ── Extensions ────────────────────────────────────────────────────────
extensions = [
    "sphinx.ext.autodoc",       # Auto-generate docs from docstrings
    "sphinx.ext.napoleon",      # Google- and NumPy-style docstring support
    "sphinx.ext.viewcode",      # Link to source code
    "sphinx.ext.intersphinx",   # Cross-reference external docs
    "sphinx.ext.todo",          # TODO directive support
    "sphinx.ext.autosummary",   # Generate summary tables
]

# ── Napoleon settings (Google-style docstrings) ───────────────────────
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True

# ── Autodoc settings ──────────────────────────────────────────────────
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "inherited-members": False,
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"

# ── Intersphinx mappings ──────────────────────────────────────────────
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "httpx": ("https://www.python-httpx.org/", None),
}

# ── HTML output ───────────────────────────────────────────────────────
html_theme = "furo"
html_title = "Terry API Docs"
html_short_title = "Terry API"
html_show_sourcelink = True
html_show_sphinx = False

# ── Misc ──────────────────────────────────────────────────────────────
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
todo_include_todos = True
add_module_names = False
python_use_unqualified_type_names = True
