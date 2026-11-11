"""Dependents, from ecosyste.ms: the strongest public sign that a package is used.

A download can be a mirror or a CI cache miss; a dependent is another package
or repository that declares yours in its manifest. ecosyste.ms (open data,
CC-BY-SA 4.0, no key needed) indexes them for every major registry:
``GET /api/v1/registries/{registry}/packages/{name}`` carries
``dependent_packages_count`` and ``dependent_repos_count``.
"""

from __future__ import annotations

import urllib.parse

from pkgreach.http import HttpError

API = "https://packages.ecosyste.ms/api/v1"
#: Ecosystem (purl type) to ecosyste.ms registry name.
REGISTRIES = {"pypi": "pypi.org", "npm": "npmjs.org", "cargo": "crates.io"}


def dependents(ecosystem: str, package: str, *, http) -> dict[str, int]:
    """``{"dependent_packages": n, "dependent_repos": m}``; ``{}`` if not indexed."""
    registry = REGISTRIES.get(ecosystem)
    if registry is None:
        return {}
    name = urllib.parse.quote(package, safe="")
    try:
        d = http(f"{API}/registries/{registry}/packages/{name}")
    except HttpError as e:
        if e.status == 404:  # not indexed (yet): unknown, not zero
            return {}
        raise
    return {
        "dependent_packages": d.get("dependent_packages_count"),
        "dependent_repos": d.get("dependent_repos_count"),
    }
