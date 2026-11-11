"""End-to-end tests of collection, summary and report against fake platforms."""

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from ghtraffic.tables import Files, read_table

from pkgreach import (
    TABLES,
    Platform,
    Selection,
    Settings,
    build_site,
    collect,
    summarize,
)
from pkgreach.config import load_settings, settings_from_mapping
from pkgreach.scaffold import CONFIG_PATH, WORKFLOW_PATH, init_repo

TODAY = date(2026, 11, 8)


def _now(d=TODAY):
    return lambda: datetime(d.year, d.month, d.day, 6, tzinfo=timezone.utc)


class FakeRegistry:
    """A registry keeping ``window`` days of daily counts for a few packages."""

    def __init__(self, counts, *, window=90, fail=()):
        self.counts, self.window, self.fail = counts, window, set(fail)
        self.calls = []

    def list_packages(self, user, *, http):
        if user == "ghost":
            raise RuntimeError("no such user")
        return [{"package": p, "deprecated": p == "old"} for p in self.counts]

    def fetch(self, record, *, http, today, since):
        name = record["package"]
        self.calls.append((name, since))
        if name in self.fail:
            raise RuntimeError("boom")
        start = max(today - timedelta(self.window), since or date.min)
        days = [start + timedelta(i) for i in range((today - start).days)]
        return {
            "downloads": [
                {"date": d.isoformat(), "series": "all", "count": self.counts[name]}
                for d in days
            ],
            "history_from": (today - timedelta(self.window)).isoformat(),
            "metrics": {"versions": 3},
            "info": {"url": f"https://example.org/{name}", "description": "<b>x</b>"},
        }

    def platform(self, name="fake", registry="fake.org"):
        return Platform(name, self.list_packages, self.fetch, registry)


def _no_deps(*a, **k):
    return {}


def _settings(**sel):
    return Settings(platforms={"fake": Selection(users=("me",), **sel)})


def test_collect_is_idempotent_and_incremental(tmp_path):
    reg = FakeRegistry({"a": 10, "b": 1, "old": 0})
    store = Files(tmp_path)
    kw = dict(platforms={"fake": reg.platform()}, http=None, dependents=_no_deps)
    r1 = collect(_settings(), store=store, now=_now(), **kw)
    assert r1.packages == {"fake": 3} and not r1.errors
    snapshot = {k: store[k] for k in store if k != "last_run.json"}
    r2 = collect(_settings(), store=store, now=_now(), **kw)
    assert r2.packages == {"fake": 3}
    # same day, same data: nothing but the run log changes
    changed = {k for k in store if k != "last_run.json" and store[k] != snapshot.get(k)}
    assert changed <= {"runs.csv"}
    # the second run asks only for the days since the last one (minus an overlap)
    assert all(since is not None for name, since in reg.calls[3:] if name == "a")
    # zero-download packages write no download rows, but are known with coverage
    rows = read_table(store, TABLES["downloads"])
    assert {r["package"] for r in rows} == {"a", "b"}
    pkgs = {r["package"]: r for r in read_table(store, TABLES["packages"])}
    assert pkgs["old"]["history_from"] == "2026-08-10"
    assert json.loads(store["manifest.json"])["tables"]["downloads"]["files"]


def test_selection_exclude_where_and_errors(tmp_path):
    reg = FakeRegistry({"a": 10, "b": 1, "old": 0, "a-test": 5}, fail={"b"})
    settings = Settings(
        platforms={
            "fake": Selection(
                users=("me", "ghost"),
                packages=("extra",),
                exclude=("*-test",),
                where={"deprecated": False},
            )
        }
    )
    reg.counts["extra"] = 2
    report = collect(
        settings,
        store=Files(tmp_path),
        platforms={"fake": reg.platform()},
        http=None,
        dependents=_no_deps,
        select=lambda platform, rec: rec["package"] != "extra",
        now=_now(),
    )
    # "old" fails `where`, "a-test" is excluded, "extra" fails `select`
    # (and has no `deprecated` key, so `where` drops it too), "b" errors
    assert report.packages == {"fake": 1}
    assert set(report.errors) == {"fake:@ghost", "fake:b"}


def test_summary_floor_growth_and_metrics(tmp_path):
    store = Files(tmp_path)
    reg = FakeRegistry({"a": 100, "b": 1, "c": 2, "d": 3})
    kw = dict(platforms={"fake": reg.platform()}, http=None)
    collect(
        _settings(),
        store=store,
        now=_now(),
        dependents=lambda *a, **k: {"dependent_packages": 4},
        **kw,
    )
    s = summarize(store, today=TODAY)
    p = s["platforms"]["fake"]
    assert p["packages"] == 4 and p["metric_totals"]["dependent_packages"] == 16
    by = {r["package"]: r for r in s["packages"]}
    assert by["a"]["downloads"]["30d"] == 3000 - 100  # today itself is not served
    assert by["a"]["x_floor"] > 10 > by["b"]["x_floor"]
    assert len(by["a"]["weekly"]) == 26
    assert by["a"]["metrics"]["versions"]["value"] == 3


def test_report_escapes_and_writes_site(tmp_path):
    store = Files(tmp_path / "data")
    reg = FakeRegistry({"a<script>": 5})
    collect(
        _settings(),
        store=store,
        platforms={"fake": reg.platform()},
        http=None,
        dependents=_no_deps,
        now=_now(),
    )
    out = Files(tmp_path / "site")
    build_site(store, out, title="Mine & yours")
    page = out["index.html"]
    assert "<script>" in page  # the sort script
    assert "a<script>" not in page and "a&lt;script&gt;" in page
    assert "<b>x</b>" not in page
    assert "Mine &amp; yours" in page
    assert json.loads(out["summary.json"])["packages"][0]["package"] == "a<script>"


def test_settings_validation(tmp_path):
    s = settings_from_mapping(
        {"pypi": {"users": "me", "where": {"fork": False}}, "max_workers": 2},
        known_platforms={"pypi"},
    )
    assert s.platforms["pypi"].users == ("me",) and s.max_workers == 2
    with pytest.raises(ValueError, match="Unknown platform"):
        settings_from_mapping({"pipy": {}}, known_platforms={"pypi"})
    with pytest.raises(ValueError, match="Unknown key"):
        settings_from_mapping({"pypi": {"user": ["me"]}})
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "missing.toml")


def test_unknown_platform_is_refused(tmp_path):
    with pytest.raises(ValueError, match="Unknown platform"):
        collect(
            Settings(platforms={"nope": Selection()}),
            store=Files(tmp_path),
            platforms={},
            http=None,
        )


def test_init_repo_writes_valid_config(tmp_path):
    written = init_repo(
        tmp_path, users={"pypi": ["me"], "github": ["me", "my-org"]}, action_ref="x@1"
    )
    assert written == [CONFIG_PATH, WORKFLOW_PATH]
    s = load_settings(tmp_path / CONFIG_PATH, known_platforms={"pypi", "github"})
    assert s.platforms["github"].where == {"fork": False, "archived": False}
    wf = (tmp_path / WORKFLOW_PATH).read_text()
    assert "uses: x@1" in wf and "${{ steps.reach.outputs.site-dir }}" in wf
    assert init_repo(tmp_path, users={"pypi": ["me"]}) == []  # never overwrites
