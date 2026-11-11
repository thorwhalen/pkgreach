"""npm: daily downloads from api.npmjs.org, listing from the registry search.

- **Listing** an account's packages: the registry search,
  ``registry.npmjs.org/-/v1/search?text=maintainer:{user}`` (250 per page).
- **Downloads**: ``api.npmjs.org/downloads/range/{start}:{end}/{name}``,
  daily, at most the last 18 months (a longer range is clipped), scoped names
  included. The first run takes all 18 months; later runs take what is new.
  A package never downloaded yet answers 404 there, which reads as zero.
- **Metadata**: from the search record (version, description, repository).
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterator
from datetime import date, timedelta

from pkgreach.http import HttpError

SEARCH_URL = "https://registry.npmjs.org/-/v1/search?text={q}&size={n}&from={start}"
RANGE_URL = "https://api.npmjs.org/downloads/range/{start}:{end}/{name}"
LATEST_URL = "https://registry.npmjs.org/{name}/latest"
PAGE_SIZE = 250
#: The download API serves the last 18 months; ask for a little more.
MAX_HISTORY_DAYS = 560
#: What the download API actually keeps (a longer range is clipped to this).
SERVED_DAYS = 540


def _clean_repo(url: str) -> str:
    url = (url or "").removeprefix("git+")
    url = url.replace("git://", "https://").replace("ssh://git@", "https://")
    return url.removesuffix(".git") if url.startswith("https://") else ""


def list_packages(user: str, *, http) -> Iterator[dict]:
    """The packages ``user`` maintains on npm."""
    q = urllib.parse.quote(f"maintainer:{user}")
    start = 0
    while True:
        got = http(SEARCH_URL.format(q=q, n=PAGE_SIZE, start=start))
        objects = got.get("objects", [])
        for o in objects:
            p = o["package"]
            yield {
                "package": p["name"],
                "_info": {
                    "url": f"https://www.npmjs.com/package/{p['name']}",
                    "repository": _clean_repo(p.get("links", {}).get("repository")),
                    "description": p.get("description") or "",
                    "latest_version": p.get("version") or "",
                },
            }
        start += len(objects)
        if not objects or start >= got.get("total", 0):
            return


def fetch(record: dict, *, http, today: date, since: date | None = None) -> dict:
    """Daily downloads and metadata of one package."""
    name = record["package"]
    start = since or today - timedelta(days=MAX_HISTORY_DAYS)
    try:
        got = http(RANGE_URL.format(start=start, end=today, name=name))
    except HttpError as e:
        if e.status != 404:
            raise
        # "package not found" here means: published, but never downloaded yet
        served = max(start, today - timedelta(days=SERVED_DAYS))
        got = {"start": served.isoformat(), "downloads": []}
    info = record.get("_info")
    if info is None:  # named in `packages`, not listed
        latest = http(LATEST_URL.format(name=name))
        repo = latest.get("repository")
        info = {
            "url": f"https://www.npmjs.com/package/{name}",
            "repository": _clean_repo(
                repo.get("url") if isinstance(repo, dict) else repo
            ),
            "description": latest.get("description") or "",
            "latest_version": latest.get("version") or "",
        }
    return {
        "downloads": [
            {"date": d["day"], "series": "all", "count": d["downloads"]}
            for d in got.get("downloads", [])
        ],
        "history_from": got.get("start", ""),  # the min with earlier runs is kept
        "info": info,
    }
