"""PyPI: daily downloads from pypistats.org, metadata from PyPI's JSON API.

- **Listing** an account's packages: PyPI's XML-RPC ``user_packages`` (the only
  official listing; deprecated, but answered). Owners and maintainers alike.
- **Downloads**: ``pypistats.org/api/packages/{name}/overall``, daily, about
  the last six months, as two series: ``all`` (with mirrors) and
  ``without_mirrors``. The analysis prefers the latter, since mirror traffic is
  pure noise. Older days are gone: hence a history kept weekly.
- **Metadata**: ``pypi.org/pypi/{name}/json`` (latest version, summary, source
  repository, first upload, number of releases).
"""

from __future__ import annotations

import re
import xmlrpc.client
from collections.abc import Iterator
from datetime import date

XMLRPC_URL = "https://pypi.org/pypi"
STATS_URL = "https://pypistats.org/api/packages/{name}/overall"
JSON_URL = "https://pypi.org/pypi/{name}/json"
#: pypistats categories to the series names stored.
SERIES = {"with_mirrors": "all", "without_mirrors": "without_mirrors"}
_REPO_KEYS = ("source", "source code", "repository", "github", "code", "homepage")


def normalize(name: str) -> str:
    """PEP 503: ``Flask_Login`` -> ``flask-login`` (pypistats only knows this form)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def list_packages(user: str, *, http) -> Iterator[dict]:
    """The packages ``user`` owns or maintains on PyPI."""
    body = xmlrpc.client.dumps((user,), "user_packages").encode("utf-8")
    text = http(XMLRPC_URL, headers={"Content-Type": "text/xml"}, data=body)
    (pairs,), _ = xmlrpc.client.loads(text)
    for role, name in pairs:
        yield {"package": name, "role": role.lower()}


def _repository(info: dict) -> str:
    urls = {k.lower(): v for k, v in (info.get("project_urls") or {}).items()}
    for k in _REPO_KEYS:
        if urls.get(k, "").startswith("https://"):
            return urls[k]
    return ""


def fetch(record: dict, *, http, today: date, since: date | None = None) -> dict:
    """Daily downloads (both series), versions, and metadata of one package."""
    name = record["package"]
    stats = http(STATS_URL.format(name=name)).get("data", [])
    lo = since.isoformat() if since else ""
    downloads = [
        {"date": r["date"], "series": SERIES[r["category"]], "count": r["downloads"]}
        for r in stats
        if r.get("category") in SERIES and r["date"] >= lo
    ]
    meta = http(JSON_URL.format(name=name))
    info, releases = meta.get("info", {}), meta.get("releases", {})
    uploads = [f["upload_time"] for files in releases.values() for f in files]
    return {
        "downloads": downloads,
        "history_from": min((r["date"] for r in stats), default=""),
        "metrics": {"versions": len(releases)},
        "info": {
            "url": f"https://pypi.org/project/{name}/",
            "repository": _repository(info),
            "description": info.get("summary") or "",
            "latest_version": info.get("version") or "",
            "created": min(uploads, default="")[:10],
        },
    }
