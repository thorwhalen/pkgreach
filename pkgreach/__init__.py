"""Track how your packages are really used, across PyPI, npm, crates.io and GitHub.

Registries keep a few months of daily download counts at most, and none of
them separates people from robots. ``pkgreach`` collects the counts every week
into a git-friendly history, adds the signals a robot does not create
(dependent packages and repositories, stars, forks), and builds a static
report that puts each package against a noise floor.

>>> from pkgreach import collect, load_settings, build_site, Files  # doctest: +SKIP
>>> collect(load_settings("pkgreach.toml"), store=Files("data"))   # doctest: +SKIP
>>> build_site(Files("data"), Files("site"))                       # doctest: +SKIP

Seams (each one keyword argument, with a working default):

- ``collect(platforms=)``: which publishing platforms (:data:`PLATFORMS`).
- :class:`Selection` per platform, plus ``collect(select=)``: which packages.
- ``collect(dependents=)``: where dependents come from (ecosyste.ms).
- ``build_site(analyze=, render=)``: what is computed and how it is shown.
- ``store`` / ``out``: where the history and the site live (any
  ``MutableMapping[str, str]``: a folder by default).
"""

from ghtraffic.tables import Files

from pkgreach.analyze import summarize
from pkgreach.collect import RunReport, collect, select_packages, write_manifest
from pkgreach.config import Selection, Settings, load_settings, settings_from_mapping
from pkgreach.http import HttpError, make_http
from pkgreach.platforms import PLATFORMS, Platform
from pkgreach.report import build_site, render_html
from pkgreach.scaffold import init_repo
from pkgreach.tables import TABLES

__all__ = [
    "Files",
    "HttpError",
    "PLATFORMS",
    "Platform",
    "RunReport",
    "Selection",
    "Settings",
    "TABLES",
    "build_site",
    "collect",
    "init_repo",
    "load_settings",
    "make_http",
    "render_html",
    "select_packages",
    "settings_from_mapping",
    "summarize",
    "write_manifest",
]
