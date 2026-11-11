"""Reading the summary, and the cells every view shares.

What a platform is (daily downloads or snapshot metrics), what it calls its
packages and which metrics it headlines come from ``summary["platforms"]``:
nothing here, or in any view, branches on a platform's name.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pkgreach.render.fmt import (
    e,
    link,
    metric,
    tab_href,
)

Summary = Mapping[str, Any]
Row = Mapping[str, Any]

#: Metrics of a daily platform shown as columns (dependents, from the
#: ``dependents=`` seam of collect); dropped when zero for every package.
DEPENDENT_METRICS = ("dependent_packages", "dependent_repos")
#: Rows a platform tab shows before "Show all".
DFLT_ROW_LIMIT = 20
#: Entries of the Overview's lists.
TOP_USED, TOP_MOVERS, TOP_DEPENDED, TOP_SNAPSHOT = 10, 8, 10, 5


# --------------------------------------------------------------------------- #
# Reading the summary


def platform_order(summary: Summary) -> list[str]:
    """Daily-download platforms first, by downloads; then snapshot ones."""
    ps = summary["platforms"]
    return sorted(ps, key=lambda n: (ps[n]["kind"] != "daily", -ps[n]["downloads_30d"]))


def rows_of(summary: Summary, platform: str) -> list[Row]:
    return [r for r in summary["packages"] if r["platform"] == platform]


def signal_x(meta: Mapping) -> float:
    return meta.get("signal_x_floor") or 3.0


def is_quiet(row: Row, meta: Mapping) -> bool:
    """Noise: under the signal threshold (daily), or every headline at zero."""
    if meta["kind"] == "snapshot":
        return not any(metric(row, m) for m in meta["headline"])
    xf = row.get("x_floor")
    return xf is None or xf < signal_x(meta)


def is_steady(row: Row, meta: Mapping) -> bool:
    """Above the signal threshold in both 30-day windows: its change means something."""
    return (
        not is_quiet(row, meta)
        and not row.get("prev_low_base")
        and row.get("growth_30d") is not None
    )


def gain(r: Row) -> int:
    return r["downloads"]["30d"] - r["downloads_prev_30d"]


def daily_platforms(summary: Summary) -> list[str]:
    return [
        p for p in platform_order(summary) if summary["platforms"][p]["kind"] == "daily"
    ]


def badge(meta: Mapping) -> str:
    return f'<span class="badge">{e(meta["title"])}</span>'


def tab_link(view: str, text: str, **params: str) -> str:
    """A link to a view: ``#tab=<view>&...`` in the page's one URL spelling."""
    return f'<a class="see" href="{tab_href(view, **params)}">{text}</a>'


def th(key: str, text: str, *, cls: str = "") -> str:
    return (
        f'<th class="{cls}" data-k="{e(key)}" aria-sort="none">'
        f'<button type="button" aria-pressed="false">{text}</button></th>'
    )


def name_cell(r: Row, chip: str = "") -> str:
    name = str(r["package"])
    return (
        f'<td class="name" data-s="{e(name.lower())}">'
        f"{link(r['url'], name, cls='nm')}{chip}</td>"
    )


def table_html(head: str, body: list[str]) -> str:
    return (
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )
