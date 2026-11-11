"""crates.io: daily downloads (last 90 days), totals and metadata.

- **Listing** an account's crates: ``/api/v1/users/{login}`` gives the user id,
  then ``/api/v1/crates?user_id={id}`` (100 per page).
- **Downloads**: ``/api/v1/crates/{name}/downloads``: per version and day for
  the last 90 days, plus ``extra_downloads`` for the older versions; summed
  per day.
- **Metadata** and all-time totals: ``/api/v1/crates/{name}``.

crates.io requires an identifying User-Agent and at most one request a second
(see :mod:`pkgreach.http`, which does both).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from datetime import date

API = "https://crates.io/api/v1"
PAGE_SIZE = 100


def list_packages(user: str, *, http) -> Iterator[dict]:
    """The crates ``user`` (a crates.io login) owns."""
    uid = http(f"{API}/users/{user}")["user"]["id"]
    page = 1
    while True:
        got = http(f"{API}/crates?user_id={uid}&per_page={PAGE_SIZE}&page={page}")
        for c in got.get("crates", []):
            yield {"package": c["name"]}
        if not got.get("meta", {}).get("next_page"):
            return
        page += 1


def fetch(record: dict, *, http, today: date, since: date | None = None) -> dict:
    """Daily downloads, totals and metadata of one crate."""
    name = record["package"]
    got = http(f"{API}/crates/{name}/downloads")
    per_day: Counter = Counter()
    for r in got.get("version_downloads", []) + got.get("meta", {}).get(
        "extra_downloads", []
    ):
        per_day[r["date"]] += r["downloads"]
    lo = since.isoformat() if since else ""
    crate = http(f"{API}/crates/{name}")
    c = crate.get("crate", {})
    return {
        "downloads": [
            {"date": d, "series": "all", "count": n}
            for d, n in sorted(per_day.items())
            if d >= lo
        ],
        "history_from": min(per_day, default=""),
        "metrics": {
            "total_downloads": c.get("downloads"),
            "versions": len(crate.get("versions") or []) or None,
        },
        "info": {
            "url": f"https://crates.io/crates/{name}",
            "repository": c.get("repository") or "",
            "description": (c.get("description") or "").strip(),
            "latest_version": c.get("max_stable_version") or c.get("max_version") or "",
            "created": (c.get("created_at") or "")[:10],
        },
    }
