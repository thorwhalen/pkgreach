"""The HTTP transport: JSON over the standard library, polite to public APIs.

Every platform takes an ``http=`` callable, ``(url, *, headers=None,
data=None) -> parsed JSON`` (or text, for non-JSON responses; ``data`` makes it
a POST), so tests and caches can stand in.
The default, :func:`make_http`, uses :mod:`urllib`, sends an identifying
``User-Agent`` (crates.io refuses requests without one), retries rate limits
and server errors with backoff, and spaces calls to the same host.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

Http = Callable[..., Any]

DFLT_USER_AGENT = "pkgreach (+https://github.com/thorwhalen/pkgreach)"
DFLT_TIMEOUT = 30
DFLT_RETRIES = 6
DFLT_BACKOFF_S = 2.0
#: Minimum seconds between two calls to the same host: crates.io asks for one a
#: second, pypistats.org allows 60 a minute, api.npmjs.org answers bursts with 429.
DFLT_MIN_INTERVAL_S = {"crates.io": 1.0, "pypistats.org": 1.0, "api.npmjs.org": 2.0}
MAX_RETRY_WAIT_S = 120.0
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class HttpError(RuntimeError):
    """An HTTP call that failed, with its status (0 for network errors)."""

    def __init__(self, status: int, message: str, *, url: str = ""):
        super().__init__(f"HTTP {status} on {url}: {message}")
        self.status, self.message, self.url = status, message, url


def _retry_after(e: urllib.error.HTTPError, attempt: int, backoff_s: float) -> float:
    """Exponential backoff, longer if the server asks (npm sends ``Retry-After: 0``)."""
    try:
        asked = float(e.headers.get("Retry-After", ""))
    except ValueError:
        asked = 0.0
    return min(max(asked, backoff_s * 2**attempt), MAX_RETRY_WAIT_S)


def make_http(
    *,
    user_agent: str = DFLT_USER_AGENT,
    timeout: float = DFLT_TIMEOUT,
    retries: int = DFLT_RETRIES,
    backoff_s: float = DFLT_BACKOFF_S,
    min_interval_s: Mapping[str, float] = DFLT_MIN_INTERVAL_S,
    sleep: Callable[[float], None] = time.sleep,
) -> Http:
    """A ``get(url, *, headers=None, data=None)`` returning parsed JSON (else text)."""
    last_call: dict[str, float] = {}
    lock = threading.Lock()

    def _space(host: str) -> None:
        interval = min_interval_s.get(host, 0.0)
        if not interval:
            return
        with lock:
            wait = last_call.get(host, 0.0) + interval - time.monotonic()
            if wait > 0:
                sleep(wait)
            last_call[host] = time.monotonic()

    def get(
        url: str, *, headers: Mapping[str, str] | None = None, data: bytes | None = None
    ) -> Any:
        host = urllib.parse.urlsplit(url).hostname or ""
        hdrs = {"User-Agent": user_agent, "Accept": "application/json"}
        hdrs.update(headers or {})
        for attempt in range(retries + 1):
            _space(host)
            req = urllib.request.Request(url, headers=hdrs, data=data)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code in _RETRY_STATUSES and attempt < retries:
                    sleep(_retry_after(e, attempt, backoff_s))
                    continue
                raise HttpError(e.code, e.reason or "", url=url) from None
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < retries:
                    sleep(backoff_s * 2**attempt)
                    continue
                raise HttpError(0, str(e), url=url) from None
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body
        raise AssertionError("unreachable")  # pragma: no cover

    return get
