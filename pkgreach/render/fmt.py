"""Small HTML and number formatters shared by the views.

Every string that came from a registry goes through :func:`e`, and
:func:`link` emits an ``<a>`` only for an ``http(s)`` URL, so a hostile
package name, description or URL renders as text.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from typing import Any


def e(s: Any) -> str:
    """HTML-escape ``s`` (quotes too, so it is safe in attributes)."""
    return html.escape(str(s), quote=True)


def link(url: str, text: str, *, cls: str = "", wbr: bool = False) -> str:
    """``<a>`` to ``url`` when it is ``http(s)``, else the escaped text.

    ``wbr``: allow a line break after each ``/`` (``owner/<wbr>repo``)."""
    c = f' class="{cls}"' if cls else ""
    t = e(text).replace("/", "/<wbr>") if wbr else e(text)
    if str(url).startswith(("https://", "http://")):
        return f'<a href="{e(url)}"{c}>{t}</a>'
    return f"<span{c}>{t}</span>"


def num(n: Any) -> str:
    """A compact count: ``1,234``, ``12k``; ``–`` for none."""
    if n is None or n == "":
        return "–"
    n = int(n)
    if abs(n) >= 10_000:
        return f"{n / 1000:,.0f}k"
    return f"{n:,}"


def full(n: Any) -> str:
    """A count with every digit: ``15,178``."""
    return "–" if n is None or n == "" else f"{int(n):,}"


def pct(x: float | None) -> str:
    """A signed percentage, coloured by sign."""
    if x is None:
        return '<span class="muted">–</span>'
    cls = "up" if x > 0 else "down" if x < 0 else "muted"
    return f'<span class="{cls}">{x:+.0%}</span>'


def times(x: float | None) -> str:
    """How many times the floor: ``1.5×``, ``1,915×``; ``–`` for none."""
    if x is None:
        return "–"
    return f"{x:,.0f}×" if x >= 10 else f"{x:g}×"


def signed(n: int | None) -> str:
    """A signed change after a value (`` +3``); nothing for none or zero."""
    if not n:
        return ""
    cls = "up" if n > 0 else "down"
    return f' <span class="{cls} small">{n:+,}</span>'


def plural(n: int, word: str, words: str | None = None) -> str:
    """``1 error``, ``2 errors``."""
    return f"{n:,} {word if n == 1 else (words or word + 's')}"


def units(n: int, unit: str) -> str:
    """``n`` of a plural ``unit``: ``1 repository``, ``343 repositories``."""
    if n != 1:
        return f"{n:,} {unit}"
    one = unit[:-3] + "y" if unit.endswith("ies") else unit.removesuffix("s")
    return f"1 {one}"


def label(metric: str) -> str:
    """How a metric name reads: ``open_issues`` -> ``open issues``."""
    return metric.replace("_", " ")


def metric(row: Mapping, name: str) -> int | None:
    """The current value of metric ``name`` of a package row, if any."""
    return row.get("metrics", {}).get(name, {}).get("value")


def spark(values: list[int], *, w: int = 120, h: int = 28) -> str:
    """An inline SVG sparkline of weekly counts (its width is set by CSS)."""
    if not values or not any(values):
        return '<span class="muted small">none</span>'
    top = max(values)
    step = w / max(1, len(values) - 1)
    pts = " ".join(
        f"{i * step:.1f},{h - 2 - (v / top) * (h - 4):.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
        f'role="img" aria-label="weekly downloads, last {len(values)} weeks">'
        f'<polyline points="{pts}" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linejoin="round" '
        'vector-effect="non-scaling-stroke"/></svg>'
    )
