from datetime import datetime


greatgramps_version = "0.3.7"

project = "greatgramps"
version = greatgramps_version
release = version
author = "Ben Nuttall"
extensions = ["sphinx_rtd_theme", "sphinx.ext.intersphinx"]
html_theme = "sphinx_rtd_theme"
copyright = "2026-%s %s" % (datetime.now().year, author)
html_title = "%s %s Documentation" % (project, version)
pygments_style = "sphinx"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.10", None),
}
