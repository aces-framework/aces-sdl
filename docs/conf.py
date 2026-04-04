# -- Project information -------------------------------------------------------

project = "ACES SDL"
copyright = "2026, ACES Framework Contributors"
author = "ACES Framework Contributors"
release = "0.1.0"

# -- General configuration -----------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
    "myst_parser",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- MyST (Markdown) settings --------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]
myst_heading_anchors = 3

# -- Options for HTML output ---------------------------------------------------

html_theme = "furo"
html_title = "ACES SDL"
html_static_path = ["_static"]

html_theme_options = {
    "source_repository": "https://github.com/aces-framework/aces-sdl",
    "source_branch": "main",
    "source_directory": "docs/",
    "navigation_with_keys": True,
}

# -- autodoc settings ----------------------------------------------------------

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_class_signature = "separated"

# -- napoleon settings ---------------------------------------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# -- intersphinx ---------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# -- autosummary ---------------------------------------------------------------

autosummary_generate = True
