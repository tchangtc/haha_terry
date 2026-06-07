"""Sphinx configuration for Terry API documentation."""
project = 'Terry'
version = '0.3.0'
author = 'Terry Contributors'
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon', 'sphinx.ext.viewcode']
html_theme = 'furo'
html_title = 'Terry API Docs'
exclude_patterns = ['_build']
