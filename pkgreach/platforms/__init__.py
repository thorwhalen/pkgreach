"""Platforms: where packages are published, and how to read their numbers.

A :class:`Platform` is three things: how to list an account's packages, how to
fetch one package's numbers, and which ecosyste.ms registry knows its
dependents. :data:`PLATFORMS` holds the built-in ones; pass your own mapping
to :func:`pkgreach.collect` to add one (conda-forge, Docker Hub, Hugging Face,
...) without changing anything else.

``list_packages(user, *, http)`` yields metadata records with at least a
``package`` key; any other keys can be used by a selection's ``where``.

``fetch(record, *, http, today, since)`` returns a dict with any of:

- ``downloads``: ``[{"date", "series", "count"}, ...]`` daily counts from
  ``since`` (``None``: as far back as the platform keeps them);
- ``history_from``: the first day the source covered (ISO date), so absent
  days after it read as zero rather than unknown;
- ``metrics``: ``{name: int}`` current values (stars, versions, total downloads);
- ``info``: metadata for the ``packages`` table (``url``, ``repository``,
  ``description``, ``latest_version``, ``created``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pkgreach.platforms import crates, github, npm, pypi


@dataclass(frozen=True)
class Platform:
    """How to list and read the packages of one publishing platform."""

    name: str
    list_packages: Callable[..., Iterable[dict]]
    fetch: Callable[..., dict[str, Any]]
    dependents_registry: str = ""  # ecosyste.ms registry name; "" for none


PLATFORMS: dict[str, Platform] = {
    p.name: p
    for p in [
        Platform("pypi", pypi.list_packages, pypi.fetch, "pypi.org"),
        Platform("npm", npm.list_packages, npm.fetch, "npmjs.org"),
        Platform("crates", crates.list_packages, crates.fetch, "crates.io"),
        Platform("github", github.list_packages, github.fetch),
    ]
}
