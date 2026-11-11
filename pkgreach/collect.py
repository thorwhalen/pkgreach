"""The collection run: select packages per platform, fetch, merge into the history.

:func:`collect` is the one orchestrator. Every table merges idempotently, so a
cold start and a weekly update are the same call, and running it twice in a
row changes nothing. One package failing never sinks a run: its error goes to
``last_run.json`` and the rest is collected.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping, MutableMapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Any

from pkgreach.config import DFLT_DATA_DIR, Selection, Settings
from pkgreach.http import Http, make_http
from pkgreach.platforms import PLATFORMS, Platform
from pkgreach.platforms.ecosystems import dependents as ecosystems_dependents
from pkgreach.tables import (
    DATA_LICENSE,
    Files,
    dump_csv,
    parse_csv,
    read_table,
    table_files,
    write_rows,
    DATA_LICENSE_KEY,
    LAST_RUN_KEY,
    MANIFEST_KEY,
    SCHEMA_VERSION,
    TABLES,
)

_log = logging.getLogger("pkgreach")
#: Days re-fetched before the last collected day: registries revise recent days.
DFLT_OVERLAP_DAYS = 7

Select = Callable[[str, Mapping[str, Any]], bool]
Dependents = Callable[..., dict[str, int]]


@dataclass
class RunReport:
    """What a run did, for logs and ``last_run.json``."""

    started_at: str
    duration_s: float = 0.0
    packages: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    files_changed: int = 0

    def summary(self) -> str:
        """One line for the log."""
        per = ", ".join(f"{p} {n}" for p, n in self.packages.items()) or "nothing"
        return (
            f"pkgreach: {per} packages; {len(self.errors)} errors, "
            f"{self.files_changed} files changed in {self.duration_s:.1f}s"
        )


def _matches(record: Mapping, where: Mapping) -> bool:
    return all(
        not k.startswith("_")
        and k in record
        and str(record[k]).lower() == str(v).lower()
        for k, v in where.items()
    )


def select_packages(
    platform: Platform,
    selection: Selection,
    *,
    http: Http,
    select: Select | None = None,
    on_error: Callable[[str, Exception], None] = lambda *_: None,
) -> dict[str, dict]:
    """The packages a selection names, as ``{name: metadata record}``.

    The users' packages that match ``where``, plus the named ones (named
    explicitly, so ``where`` does not apply to them), minus ``exclude``
    patterns, keeping those ``select`` accepts. Names are normalized by the
    platform (PyPI: ``Flask_Login`` and ``flask-login`` are one package).
    """
    norm = platform.normalize
    records: dict[str, dict] = {}
    for user in selection.users:
        try:
            for r in platform.list_packages(user, http=http):
                if _matches(r, selection.where):
                    records.setdefault(
                        norm(r["package"]), {**r, "package": norm(r["package"])}
                    )
        except Exception as e:  # noqa: BLE001 - one account never sinks the run
            on_error(f"{platform.name}:@{user}", e)
    for name in selection.packages:
        records.setdefault(norm(name), {"package": norm(name)})
    return {
        name: r
        for name, r in sorted(records.items())
        if not any(fnmatch(name, pat) for pat in selection.exclude)
        and (select is None or select(platform.name, r))
    }


def _last_dates(store: MutableMapping, platform: str) -> dict[str, str]:
    """The last day with downloads, per package, from the last two year files."""
    files = table_files(store, TABLES["downloads"])[-2:]
    years = {f.split("/")[-1][:4] for f in files}
    last: dict[str, str] = {}
    for r in read_table(store, TABLES["downloads"], years=years):
        if r["platform"] == platform:
            last[r["package"]] = max(last.get(r["package"], ""), str(r["date"]))
    return last


def _prune(store: MutableMapping, platform: str, *, keep: set[str]) -> int:
    """Remove a platform's packages that are no longer followed from the
    ``packages`` and ``metrics`` tables (a repo made private must disappear
    from a public history). Returns the number of files changed."""
    changed = 0
    for name in ("packages", "metrics"):
        spec = TABLES[name]
        for path in table_files(store, spec):
            text = store[path]
            rows = parse_csv(spec, text)
            kept = [
                r for r in rows if r["platform"] != platform or r["package"] in keep
            ]
            if len(kept) != len(rows):
                store[path] = dump_csv(spec, kept)
                changed += 1
    return changed


def write_manifest(store: MutableMapping, *, updated: str) -> dict:
    """Write ``manifest.json``: the schema and the files of every table."""
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "updated": updated,
        "tables": {
            name: {
                "files": table_files(store, spec),
                "columns": list(spec.columns),
                "key": list(spec.key),
                "description": spec.description,
            }
            for name, spec in TABLES.items()
        },
    }
    text = json.dumps(manifest, indent=2) + "\n"
    if store.get(MANIFEST_KEY) != text:
        store[MANIFEST_KEY] = text
    return manifest


def collect(
    settings: Settings,
    *,
    store: MutableMapping | None = None,
    platforms: Mapping[str, Platform] = PLATFORMS,
    http: Http | None = None,
    select: Select | None = None,
    dependents: Dependents = ecosystems_dependents,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    log: Callable[[str], None] = _log.info,
) -> RunReport:
    """Run one collection into ``store`` and return its report.

    Args:
        settings: what to collect (:func:`~pkgreach.config.load_settings`).
        store: where the history lives; default ``~/.local/share/pkgreach/data``.
        platforms: name to :class:`~pkgreach.platforms.Platform`; add one here
            to support a new registry without touching anything else.
        http: the transport (default :func:`~pkgreach.http.make_http`).
        select: ``(platform, metadata) -> keep?``, on top of the settings.
        dependents: ``(ecosystem, package, *, http) -> {metric: count}``; the
            default asks ecosyste.ms for dependent packages and repositories.
        now: the clock; log: where the one-line summary goes.
    """
    store = Files(DFLT_DATA_DIR) if store is None else store
    http = http or make_http()
    t0 = time.monotonic()
    started = now()
    today = started.date()
    report = RunReport(started_at=started.isoformat(timespec="seconds"))
    rows: dict[str, list[dict]] = {name: [] for name in TABLES}
    old_packages = {
        (r["platform"], r["package"]): r for r in read_table(store, TABLES["packages"])
    }
    unknown = sorted(set(settings.platforms) - set(platforms))
    if unknown:
        raise ValueError(f"Unknown platform(s) {unknown}; known: {sorted(platforms)}")

    def on_error(where: str, e: Exception) -> None:
        report.errors[where] = f"{type(e).__name__}: {e}"

    for pname, selection in settings.platforms.items():
        platform = platforms[pname]
        chosen = select_packages(
            platform, selection, http=http, select=select, on_error=on_error
        )
        last = _last_dates(store, pname)

        def one(item: tuple[str, dict]):
            name, record = item
            since = None
            if name in last:
                since = date.fromisoformat(last[name]) - timedelta(DFLT_OVERLAP_DAYS)
            got = platform.fetch(record, http=http, today=today, since=since)
            if settings.dependents and platform.ecosystem:
                try:  # a dependents outage never costs the downloads
                    deps = dependents(platform.ecosystem, name, http=http)
                    got["metrics"] = {**deps, **got.get("metrics", {})}
                except Exception as e:  # noqa: BLE001 - recorded, run goes on
                    got["dependents_error"] = e
            return got

        def safely(item):
            try:
                return item[0], one(item), None
            except Exception as e:  # noqa: BLE001 - recorded per package
                return item[0], None, e

        n_ok = n_err = 0
        listing_ok = not any(k.startswith(f"{pname}:@") for k in report.errors)
        with ThreadPoolExecutor(max_workers=max(1, settings.max_workers)) as pool:
            for name, got, err in pool.map(safely, chosen.items()):
                old = old_packages.get((pname, name), {})
                if err is not None:
                    on_error(f"{pname}:{name}", err)
                    n_err += 1
                    # still followed: keep it current, with what we knew
                    rows["packages"].append(
                        {
                            **old,
                            "platform": pname,
                            "package": name,
                            "first_seen": old.get("first_seen") or today.isoformat(),
                            "last_seen": today.isoformat(),
                        }
                    )
                    continue
                n_ok += 1
                if "dependents_error" in got:
                    on_error(f"{pname}:{name}:dependents", got["dependents_error"])
                rows["downloads"] += [
                    {"platform": pname, "package": name, **r}
                    for r in got.get("downloads", [])
                    if r["count"]
                ]
                rows["metrics"] += [
                    {"date": today.isoformat(), "platform": pname, "package": name}
                    | {"metric": m, "value": v}
                    for m, v in got.get("metrics", {}).items()
                    if v is not None
                ]
                fetched_from = got.get("history_from", "")
                rows["packages"].append(
                    {
                        **got.get("info", {}),
                        "platform": pname,
                        "package": name,
                        "history_from": min(
                            filter(None, [old.get("history_from"), fetched_from]),
                            default="",
                        ),
                        "first_seen": old.get("first_seen") or today.isoformat(),
                        "last_seen": today.isoformat(),
                    }
                )
        report.packages[pname] = n_ok
        if platform.prune_unlisted and listing_ok:
            report.files_changed += _prune(store, pname, keep=set(chosen))
        rows["runs"].append(
            {
                "started_at": report.started_at,
                "platform": pname,
                "packages": n_ok,
                "errors": n_err,
            }
        )

    report.duration_s = round(time.monotonic() - t0, 1)
    for r in rows["runs"]:
        r["duration_s"] = report.duration_s
    for name, spec in TABLES.items():
        if rows[name]:
            report.files_changed += write_rows(store, spec, rows[name])
    store[LAST_RUN_KEY] = json.dumps(asdict(report), indent=2) + "\n"
    if store.get(DATA_LICENSE_KEY) != DATA_LICENSE:
        store[DATA_LICENSE_KEY] = DATA_LICENSE
    write_manifest(store, updated=today.isoformat())
    log(report.summary())
    return report
