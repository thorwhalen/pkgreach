"""The schema of a pkgreach data directory: long-form CSV tables, one per kind.

Every platform writes the same tables, with a ``platform`` column, so adding a
platform never changes the schema. The CSV machinery (year partitions,
idempotent merges, the ``MutableMapping`` store) is ghtraffic's
(:mod:`ghtraffic.tables`): the history of a package's downloads has the same
shape, and the same merge problem, as the history of a repo's views.

- ``downloads``: daily counts, merged by **max** per ``(date, platform,
  package, series)``. Registries recompute recent days, and windows overlap
  between runs; max makes re-runs and overlaps harmless. ``series`` separates
  variants of one count (``all``; ``without_mirrors`` on PyPI).
- ``metrics``: slowly changing numbers (dependents, stars, versions, total
  downloads), one row per **change** per ``(platform, package, metric)``.
- ``packages``: current metadata of every package seen (kept after it is
  dropped from the selection, with its ``last_seen``). ``history_from`` is the
  first day its downloads were collected for: before it, a day is unknown;
  from it on, a missing ``downloads`` row means zero.
- ``runs``: one row per collection run.
"""

from __future__ import annotations

from ghtraffic.tables import TableSpec

SCHEMA_VERSION = 1
MANIFEST_KEY = "manifest.json"
LAST_RUN_KEY = "last_run.json"
SUMMARY_KEY = "summary.json"

TABLES: dict[str, TableSpec] = {
    t.name: t
    for t in [
        TableSpec(
            "downloads",
            ("date", "platform", "package", "series", "count"),
            key=("date", "platform", "package", "series"),
            merge="max",
            int_columns=("count",),
            time_column="date",
            description="Daily downloads per package; days with zero downloads "
            "are absent (from the package's history_from on, absence means zero).",
        ),
        TableSpec(
            "metrics",
            ("date", "platform", "package", "metric", "value"),
            key=("date", "platform", "package", "metric"),
            merge="change_only",
            entity=("platform", "package", "metric"),
            int_columns=("value",),
            description="Slowly changing numbers (dependents, stars, forks, "
            "versions, total downloads), one row per change.",
            sort=("platform", "package", "metric", "date"),
        ),
        TableSpec(
            "packages",
            (
                "platform",
                "package",
                "url",
                "repository",
                "description",
                "latest_version",
                "created",
                "history_from",
                "first_seen",
                "last_seen",
            ),
            key=("platform", "package"),
            merge="upsert",
            description="Current metadata of every package seen.",
        ),
        TableSpec(
            "runs",
            ("started_at", "duration_s", "platform", "packages", "errors"),
            key=("started_at", "platform"),
            merge="upsert",
            int_columns=("packages", "errors"),
            description="One row per collection run and platform.",
        ),
    ]
}
