import os
import sys

sys.path.insert(0, os.path.abspath(".."))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
project = "Agent Catalog"
copyright = "2025, Couchbase"
author = "Couchbase"
release = "v0.2.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "enum_tools.autoenum",
    "sphinxcontrib.autodoc_pydantic",
    "sphinx_copybutton",
    "sphinx.ext.githubpages",
    "click_extra.sphinx",
]
pygments_style = "sphinx"
templates_path = ["_templates"]
exclude_patterns = []
nitpicky = True

# -- Options for AutoDoc -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html
autodoc_default_options = {"exclude-members": "model_post_init"}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "collapse_navigation": False,
}
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_favicon = "_static/favicon.png"
