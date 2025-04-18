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
    "sphinx.ext.githubpages",
    "sphinxcontrib.autodoc_pydantic",
    "sphinxcontrib.mermaid",
    "sphinx_copybutton",
    "sphinx_design",
    "enum_tools.autoenum",
    "click_extra.sphinx",
]
pygments_style = "sphinx"
templates_path = ["_templates"]
exclude_patterns = ["_unused/*"]
smartquotes = False
# nitpicky = True

# -- Options for AutoDoc -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html
autodoc_default_options = {"exclude-members": "model_post_init"}
autodoc_typehints = "description"
autodoc_pydantic_model_show_json_error_strategy = "coerce"
autodoc_pydantic_settings_show_json_error_strategy = "coerce"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
# https://piccolo-theme.readthedocs.io/en/latest/
html_theme = "piccolo_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_favicon = "_static/favicon.png"
