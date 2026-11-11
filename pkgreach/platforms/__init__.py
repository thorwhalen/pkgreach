"""Platforms: where packages are published, and how to read their numbers.

A :class:`Platform` says how to list an account's packages, how to fetch one
package's numbers, and how the report should present them. :data:`PLATFORMS`
holds the built-in ones; pass your own mapping to :func:`pkgreach.collect`
and :func:`pkgreach.summarize` to add one (conda-forge, Docker Hub, Hugging
Face, ...). Nothing else changes: the analysis and the report read only the
fields below, never a platform's name.

``list_packages(user, *, http)`` yields metadata records with at least a
``package`` key. Other plain keys (``fork``, ``role``, ...) can be matched by
a selection's ``where``. A listing that already carries the numbers may put
them under ``_info`` and ``_metrics``, so that ``fetch`` needs no further call
(GitHub does); keys starting with ``_`` are never matched by ``where``.

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

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pkgreach.platforms import crates, github, npm, pypi


@dataclass(frozen=True)
class Platform:
    """How to list and read the packages of one publishing platform.

    Attributes:
        name: the key in ``pkgreach.toml`` and in the tables' ``platform`` column.
        list_packages, fetch: see the module docstring.
        title: how the report names it.
        kind: ``"daily"`` if ``fetch`` returns daily downloads (the report shows
            windows, growth and the noise floor), ``"snapshot"`` if it returns
            current values only (the report shows ``headline`` metrics).
        headline: the metrics a snapshot platform's table and card show, the
            first one summed on the card.
        unit: what the report calls this platform's packages (plural).
        preferred_series: download series to analyse, best first.
        ecosystem: the package ecosystem, as a purl type (``pypi``, ``npm``,
            ``cargo``), for dependents lookups; ``""`` for none.
        default_where: the ``where`` that ``pkgreach init`` writes for it.
        normalize: canonical form of a package name (PyPI: PEP 503).
        prune_unlisted: remove packages no longer listed from the history's
            current tables (for GitHub: a repo made private must not stay in a
            public history).
    """

    name: str
    list_packages: Callable[..., Iterable[dict]]
    fetch: Callable[..., dict[str, Any]]
    title: str = ""
    kind: Literal["daily", "snapshot"] = "daily"
    headline: tuple[str, ...] = ()
    unit: str = "packages"
    preferred_series: tuple[str, ...] = ("all",)
    ecosystem: str = ""
    default_where: Mapping[str, Any] = field(default_factory=dict)
    normalize: Callable[[str], str] = str
    prune_unlisted: bool = False


PLATFORMS: dict[str, Platform] = {
    p.name: p
    for p in [
        Platform(
            "pypi",
            pypi.list_packages,
            pypi.fetch,
            title="PyPI",
            preferred_series=("without_mirrors", "all"),
            ecosystem="pypi",
            normalize=pypi.normalize,
        ),
        Platform("npm", npm.list_packages, npm.fetch, title="npm", ecosystem="npm"),
        Platform(
            "crates",
            crates.list_packages,
            crates.fetch,
            title="crates.io",
            ecosystem="cargo",
        ),
        Platform(
            "github",
            github.list_packages,
            github.fetch,
            title="GitHub",
            kind="snapshot",
            headline=("stars", "forks", "open_issues"),
            unit="repositories",
            default_where={"fork": False, "archived": False},
            prune_unlisted=True,
        ),
    ]
}
