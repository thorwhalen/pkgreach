"""From the history to a summary: windowed totals, growth, and a noise floor.

:func:`summarize` turns the tables into one JSON-ready dict, which the report
renders and anyone can consume (``summary.json``). It is the default of the
``analyze=`` seam of :func:`pkgreach.report.build_site`.

Download counts are mostly not people. Mirrors, CI pipelines, scanners and
bots download every release of every package, so a package nobody uses still
gets a steady trickle. The summary therefore puts each package against a
**noise floor**: the 25th percentile of 30-day downloads among the packages
you follow on that platform that were downloaded at all (an estimate of what
an unused package of yours gets). ``x_floor`` is a package's 30-day downloads over that floor; dependents
and stars, which a bot does not create, are reported next to it.

On PyPI the ``without_mirrors`` series (from pypistats.org) is used when it
exists, since mirror traffic is pure noise.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, MutableMapping
from datetime import date, timedelta
from statistics import quantiles
from typing import Any

from ghtraffic.tables import read_table

from pkgreach.tables import TABLES

#: Windows (days) the summary totals over.
WINDOWS = (7, 30, 90, 365)
#: Series preferred per platform, first match wins; others fall back to "all".
PREFERRED_SERIES: Mapping[str, tuple[str, ...]] = {"pypi": ("without_mirrors", "all")}
DFLT_FLOOR_QUANTILE = 0.25
SPARK_WEEKS = 26


def _daily(store: MutableMapping) -> dict[tuple[str, str], dict[str, int]]:
    """``{(platform, package): {date: count}}``, in each platform's preferred series."""
    by_series: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
    for r in read_table(store, TABLES["downloads"]):
        key = (r["platform"], r["package"], r["series"])
        by_series[key][str(r["date"])] = int(r["count"])
    best: dict[tuple[str, str], tuple[int, str]] = {}
    for platform, package, series in by_series:
        prefs = PREFERRED_SERIES.get(platform, ("all",))
        rank = prefs.index(series) if series in prefs else len(prefs)
        if rank < best.get((platform, package), (len(prefs) + 1, ""))[0]:
            best[(platform, package)] = (rank, series)
    return {k: by_series[(*k, series)] for k, (_, series) in best.items()}


def _window(days: Mapping[str, int], end: date, n: int) -> int:
    start = (end - timedelta(days=n - 1)).isoformat()
    stop = end.isoformat()
    return sum(c for d, c in days.items() if start <= d <= stop)


def _weekly(days: Mapping[str, int], end: date, weeks: int) -> list[int]:
    return [
        _window(days, end - timedelta(days=7 * (weeks - 1 - i)), 7)
        for i in range(weeks)
    ]


def _metrics(store: MutableMapping, today: date, delta_days: int = 30):
    """``{(platform, package): {metric: {"value", "change_30d"}}}``."""
    hist: dict[tuple, list[tuple[str, int]]] = defaultdict(list)
    for r in read_table(store, TABLES["metrics"]):
        if r["value"] != "":
            hist[(r["platform"], r["package"], r["metric"])].append(
                (str(r["date"]), int(r["value"]))
            )
    cutoff = (today - timedelta(days=delta_days)).isoformat()
    out: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for (platform, package, metric), pts in hist.items():
        pts.sort()
        value = pts[-1][1]
        before = [v for d, v in pts if d <= cutoff]
        out[(platform, package)][metric] = {
            "value": value,
            "change_30d": value - before[-1] if before else None,
        }
    return out


def _floor(values: list[int], q: float) -> int:
    values = sorted(values)
    if not values:
        return 0
    if len(values) < 4:
        return values[0]
    return int(quantiles(values, n=100, method="inclusive")[int(q * 100) - 1])


def summarize(
    store: MutableMapping,
    *,
    today: date | None = None,
    floor_quantile: float = DFLT_FLOOR_QUANTILE,
) -> dict[str, Any]:
    """A JSON-ready summary of the history in ``store``."""
    packages = {
        (r["platform"], r["package"]): r for r in read_table(store, TABLES["packages"])
    }
    daily = _daily(store)
    end_candidates = [max(d) for d in daily.values() if d]
    today = today or (
        date.fromisoformat(max(end_candidates)) if end_candidates else date.today()
    )
    metrics = _metrics(store, today)
    rows = []
    for key in sorted(set(packages) | set(daily) | set(metrics)):
        platform, package = key
        days = daily.get(key, {})
        info = packages.get(key, {})
        row = {
            "platform": platform,
            "package": package,
            "url": info.get("url", ""),
            "repository": info.get("repository", ""),
            "description": info.get("description", ""),
            "latest_version": info.get("latest_version", ""),
            "history_from": info.get("history_from", ""),
            "last_seen": info.get("last_seen", ""),
            "downloads": {f"{n}d": _window(days, today, n) for n in WINDOWS},
            "downloads_prev_30d": _window(days, today - timedelta(days=30), 30),
            "downloads_collected": sum(days.values()),
            "has_downloads": bool(days or info.get("history_from")),
            "weekly": _weekly(days, today, SPARK_WEEKS) if days else [],
            "metrics": metrics.get(key, {}),
        }
        prev = row["downloads_prev_30d"]
        row["growth_30d"] = (
            round(row["downloads"]["30d"] / prev - 1, 3) if prev else None
        )
        rows.append(row)

    platforms: dict[str, dict] = {}
    for platform in sorted({r["platform"] for r in rows}):
        mine = [r for r in rows if r["platform"] == platform]
        # packages with no download at all say nothing about the noise level
        with_dl = [r["downloads"]["30d"] for r in mine if r["downloads"]["30d"]]
        floor = _floor(with_dl, floor_quantile)
        for r in mine:
            r["x_floor"] = (
                round(r["downloads"]["30d"] / floor, 1)
                if floor and r["has_downloads"]
                else None
            )
        platforms[platform] = {
            "packages": len(mine),
            "downloads_30d": sum(r["downloads"]["30d"] for r in mine),
            "downloads_prev_30d": sum(r["downloads_prev_30d"] for r in mine),
            "noise_floor_30d": floor if with_dl else None,
            "metric_totals": {
                m: sum(r["metrics"].get(m, {}).get("value", 0) for r in mine)
                for m in sorted({m for r in mine for m in r["metrics"]})
            },
        }
    return {"as_of": today.isoformat(), "platforms": platforms, "packages": rows}
