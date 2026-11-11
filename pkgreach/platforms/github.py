"""GitHub: public repositories, with stars, forks and open issues.

Only **public** repositories are followed, whatever the token can see: this
report is meant to be publishable. Traffic (views, clones, referrers) needs
push access and is private; that is ghtraffic's job
(https://github.com/thorwhalen/ghtraffic), kept in a private repository.

Listing uses ``GET /users/{owner}/repos`` (users and organizations alike), one
call per 100 repos, and the listing already carries the numbers, so fetching
costs no further call. A token only raises the rate limit (60 calls an hour
without one); it reaches the requests through the transport
(``make_http(headers_by_host=auth_headers(token))``), never from here.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date

API = "https://api.github.com"
HOST = "api.github.com"
PAGE_SIZE = 100
TOKEN_ENV_VARS = ("GITHUB_TOKEN", "GH_TOKEN")
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def auth_headers(token: str | None) -> dict[str, Mapping[str, str]]:
    """``headers_by_host`` for :func:`pkgreach.http.make_http`: the token, for GitHub only."""
    return {HOST: {"Authorization": f"Bearer {token}"}} if token else {}


def token_from_env(environ: Mapping[str, str]) -> str:
    """The first of ``GITHUB_TOKEN``, ``GH_TOKEN`` set in ``environ``, or ``""``."""
    return next((environ[v] for v in TOKEN_ENV_VARS if environ.get(v)), "")


def _record(r: dict) -> dict:
    return {
        "package": r["full_name"],
        "private": r.get("private", False),
        "fork": r.get("fork", False),
        "archived": r.get("archived", False),
        "language": r.get("language") or "",
        "_info": {
            "url": r.get("html_url", ""),
            "repository": r.get("html_url", ""),
            "description": r.get("description") or "",
            "created": (r.get("created_at") or "")[:10],
        },
        "_metrics": {
            "stars": r.get("stargazers_count"),
            "forks": r.get("forks_count"),
            "open_issues": r.get("open_issues_count"),  # issues + pull requests
        },
    }


def list_packages(user: str, *, http) -> Iterator[dict]:
    """The public repos owned by ``user`` (a user or an organization)."""
    page = 1
    while True:
        got = http(
            f"{API}/users/{user}/repos?type=owner&per_page={PAGE_SIZE}&page={page}",
            headers=_HEADERS,
        )
        for r in got:
            if not r.get("private", False):
                yield _record(r)
        if len(got) < PAGE_SIZE:
            return
        page += 1


def fetch(record: dict, *, http, today: date, since: date | None = None) -> dict:
    """Stars, forks and open issues of one public repo."""
    if "_metrics" not in record:  # named in `packages`, not listed
        r = http(f"{API}/repos/{record['package']}", headers=_HEADERS)
        if r.get("private", False):
            raise ValueError("private repository: not followed (public report)")
        record = _record(r)
    return {"metrics": dict(record["_metrics"]), "info": dict(record["_info"])}
