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

Growth over the prior 30 days is also mostly not people: a platform whose bots
all doubled their pace doubles every package. So each package's growth is also
given relative to its platform's median (``growth_vs_median_30d``), a package
whose prior window was under ``signal_x_floor`` times the floor is marked
``prev_low_base`` (its percentages are noise), and growth is ``None`` when the
history does not cover the whole prior window.

On PyPI the ``without_mirrors`` series (from pypistats.org) is used when it
exists, since mirror traffic is pure noise.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, MutableMapping
from datetime import date, timedelta
from statistics import median, quantiles
from typing import Any

from pkgreach.platforms import PLATFORMS, Platform
from pkgreach.tables import LAST_RUN_KEY, TABLES, read_table

#: Windows (days) the summary totals over.
WINDOWS = (7, 30, 90, 365)
DFLT_FLOOR_QUANTILE = 0.25
#: How many times the noise floor a 30-day count must reach to count as signal.
DFLT_SIGNAL_X_FLOOR = 3.0
#: Where the numbers come from, and on what terms (ecosyste.ms is CC BY-SA 4.0).
ATTRIBUTION = {
    "downloads": "pypistats.org, api.npmjs.org, crates.io",
    "dependents": "ecosyste.ms (https://ecosyste.ms), CC BY-SA 4.0 "
    "(https://creativecommons.org/licenses/by-sa/4.0/), aggregated",
    "github": "GitHub REST API, public repositories only",
}
SPARK_WEEKS = 26


def _daily(
    store: MutableMapping, prefs_of: Mapping[str, tuple[str, ...]]
) -> dict[tuple[str, str], dict[str, int]]:
    """``{(platform, package): {date: count}}`` in one series per platform.

    The series is the platform's most preferred one present for any package,
    then used for all of them: zero days are not stored, so a package that a
    preferred series counts as zero (all its PyPI downloads are mirrors) must
    read as zero, not fall back to a noisier series.
    """
    by_series: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
    for r in read_table(store, TABLES["downloads"]):
        key = (r["platform"], r["package"], r["series"])
        by_series[key][str(r["date"])] = int(r["count"])
    present: dict[str, set[str]] = defaultdict(set)
    for platform, _, series in by_series:
        present[platform].add(series)
    chosen = {}
    for platform, series_set in present.items():
        prefs = prefs_of.get(platform, ("all",))
        chosen[platform] = next(
            (x for x in prefs if x in series_set), sorted(series_set)[0]
        )
    return {
        (platform, package): days
        for (platform, package, series), days in by_series.items()
        if series == chosen[platform]
    }


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
    idx = min(99, max(1, round(q * 100))) - 1
    return int(quantiles(values, n=100, method="inclusive")[idx])


def _current(packages: Mapping[tuple[str, str], Mapping]) -> set[tuple[str, str]]:
    """The packages the latest run of their platform still followed.

    A package dropped from the selection, deleted, or (for a repo) made private
    leaves the report, though its past rows stay in the history.
    """
    last_run: dict[str, str] = {}
    for (platform, _), r in packages.items():
        last_run[platform] = max(last_run.get(platform, ""), r.get("last_seen", ""))
    return {k for k, r in packages.items() if r.get("last_seen", "") == last_run[k[0]]}


def _ends(packages, daily) -> dict[str, date]:
    """Per platform, the last complete day: its last day with downloads, but
    never the day of its last run (crates.io serves the partial current day,
    pypistats and npm stop a day or two earlier)."""
    last_run: dict[str, str] = {}
    for (platform, _), r in packages.items():
        last_run[platform] = max(last_run.get(platform, ""), r.get("last_seen", ""))
    last_day: dict[str, str] = {}
    for (platform, _), days in daily.items():
        if days:
            last_day[platform] = max(last_day.get(platform, ""), max(days))
    ends = {}
    for platform, d in last_day.items():
        end = date.fromisoformat(d)
        if last_run.get(platform):
            end = min(end, date.fromisoformat(last_run[platform]) - timedelta(days=1))
        ends[platform] = end
    return ends


def _followed_from(info: Mapping, days: Mapping[str, int]) -> str:
    """The first day a package's counts can be trusted to cover: the later of
    the source's first day (``history_from``) and the package's creation, or,
    when the registry gives no creation date, its first day with downloads
    (``""``: unknown)."""
    born = str(info.get("created") or "")[:10] or (min(days) if days else "")
    return max(str(info.get("history_from") or ""), born)


def _covers(start_day: str, end: date, n: int) -> bool:
    """Whether a history starting on ``start_day`` covers the ``n`` days to
    ``end`` (unknown start: assumed covered, as the stored days are all we have)."""
    start = (end - timedelta(days=n - 1)).isoformat()
    return not start_day or start_day <= start


def _median_growth(rows: list[Mapping]) -> float | None:
    """The median growth of the packages whose growth means something: a
    covered prior window above the low-base threshold."""
    gs = [
        r["growth_30d"]
        for r in rows
        if r["growth_30d"] is not None and not r["prev_low_base"]
    ]
    return round(median(gs), 3) if gs else None


def _run_errors(store: MutableMapping) -> int | None:
    try:
        return len(json.loads(store[LAST_RUN_KEY]).get("errors", {}))
    except (KeyError, ValueError):
        return None


def summarize(
    store: MutableMapping,
    *,
    platforms: Mapping[str, Platform] = PLATFORMS,
    today: date | None = None,
    floor_quantile: float = DFLT_FLOOR_QUANTILE,
    signal_x_floor: float = DFLT_SIGNAL_X_FLOOR,
) -> dict[str, Any]:
    """A JSON-ready summary of the history in ``store``.

    ``platforms`` supplies how each platform is presented (title, kind,
    headline metrics, preferred download series); a platform in the history
    but not in ``platforms`` is shown as a daily-downloads platform.
    ``signal_x_floor``: below this many times the noise floor, a 30-day count
    is treated as noise (``prev_low_base``, and the report dims the row).
    """

    def spec(name: str) -> Platform:
        return platforms.get(name) or Platform(name, list, dict, title=name)

    packages = {
        (r["platform"], r["package"]): r for r in read_table(store, TABLES["packages"])
    }
    known = {name for name, _ in packages}
    daily = _daily(store, {n: spec(n).preferred_series for n in known})
    ends = _ends(packages, daily)
    as_of = today or max(ends.values(), default=date.today())
    metrics = _metrics(store, as_of)
    rows = []
    for key in sorted(_current(packages)):
        platform, package = key
        end = today or ends.get(platform, as_of)
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
            "downloads": {f"{n}d": _window(days, end, n) for n in WINDOWS},
            "downloads_prev_30d": _window(days, end - timedelta(days=30), 30),
            "prev_covered": _covers(_followed_from(info, days), end, 60),
            "downloads_collected": sum(days.values()),
            "has_downloads": bool(days or info.get("history_from")),
            "weekly": _weekly(days, end, SPARK_WEEKS) if days else [],
            "metrics": metrics.get(key, {}),
        }
        prev = row["downloads_prev_30d"]
        row["growth_30d"] = (
            round(row["downloads"]["30d"] / prev - 1, 3)
            if prev and row["prev_covered"]
            else None
        )
        rows.append(row)

    by_platform: dict[str, dict] = {}
    for platform in sorted({r["platform"] for r in rows}):
        p = spec(platform)
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
            r["prev_low_base"] = bool(
                floor
                and r["has_downloads"]
                and r["downloads_prev_30d"] < signal_x_floor * floor
            )
        med = _median_growth(mine)
        for r in mine:
            g = r["growth_30d"]
            r["growth_vs_median_30d"] = (
                round((1 + g) / (1 + med) - 1, 3)
                if g is not None and med is not None and med > -1
                else None
            )
        total = sum(r["downloads"]["30d"] for r in mine)
        # growth over the packages followed through both windows only
        covered = [r for r in mine if r["prev_covered"]]
        cur_c = sum(r["downloads"]["30d"] for r in covered)
        prev_c = sum(r["downloads_prev_30d"] for r in covered)
        by_platform[platform] = {
            "title": p.title or platform,
            "kind": p.kind,
            "headline": list(p.headline),
            "unit": p.unit,
            "packages": len(mine),
            "downloads_30d": total,
            "downloads_prev_30d": sum(r["downloads_prev_30d"] for r in mine),
            "growth_30d": round(cur_c / prev_c - 1, 3) if prev_c else None,
            "median_growth_30d": med,
            "noise_floor_30d": floor if with_dl else None,
            "signal_x_floor": signal_x_floor,
            "metric_totals": {
                m: sum(r["metrics"].get(m, {}).get("value", 0) for r in mine)
                for m in sorted({m for r in mine for m in r["metrics"]})
            },
        }
    return {
        "as_of": as_of.isoformat(),
        "last_run_errors": _run_errors(store),
        "attribution": ATTRIBUTION,
        "platforms": by_platform,
        "packages": rows,
    }
