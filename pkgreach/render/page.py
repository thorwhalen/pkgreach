"""The default page: one ``index.html`` holding every view, data baked in.

Views: ``overview`` (cards and short lists), one per platform (its table,
searchable and sortable), ``all`` (every table, full length: also what a
browser without JavaScript shows), ``projects`` (packages joined to their
repository) and ``movers`` (who gained and lost downloads). ``default_view``
picks the one a bare URL opens.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pkgreach.render.assets import CSS, JS
from pkgreach.render.fmt import e, link, plural
from pkgreach.render.views import (
    movers,
    overview,
    platform_order,
    platform_section,
    projects,
    rows_of,
)

DFLT_TITLE = "Package reach"
DFLT_VIEW = "overview"
#: The views that are not a platform, in tab-bar order (the first is the
#: default's default; the rest sit behind ``⋯`` on a phone).
FIXED_VIEWS = ("overview", "all", "projects", "movers")
_MORE_VIEWS = {"all": "All", "projects": "Projects", "movers": "Movers"}

HOW_TO_READ = """
<details id="how"><summary>How to read these numbers</summary>
<p><b>Downloads are mostly not people.</b> Mirrors, CI pipelines, security
scanners and bots fetch every release of every package, so a package nobody
uses still gets a steady trickle. The <b>noise floor</b> is the 25th percentile
of 30-day downloads among the packages followed here that were downloaded at
all; <b>× floor</b> says how far above it a package is. A package near 1× is
probably only seen by robots, and rows under 3× are dimmed.</p>
<p><b>Change</b> is shown against the platform's median package: when robot
traffic doubles across a registry, every package doubles, and that says nothing
about yours. A package that was under 3× the floor in the prior 30 days is
marked <i>low base</i>; one not followed for the whole prior window, <i>new</i>.</p>
<p><b>The strongest signs of real use</b> are the ones a robot does not create:
<b>dependents</b> (other packages and repositories that declare it, from
ecosyste.ms), stars and forks, and issues opened by people other than you.</p>
<p>PyPI counts exclude known mirrors (pypistats.org's <i>without_mirrors</i>).
Registries keep only a few months of daily counts, so this history starts at
each package's first collection.</p></details>
"""


def views_of(summary: Mapping[str, Any]) -> list[str]:
    """Every view name the page for ``summary`` accepts as ``default_view``."""
    return [FIXED_VIEWS[0], *platform_order(summary), *FIXED_VIEWS[1:]]


def _status(summary: Mapping) -> str:
    n = summary.get("last_run_errors")
    if n is None:
        return ""
    text = plural(n, "error") if n else "no errors"
    cls = ' class="down"' if n else ""
    return f' · <a href="last_run.json"{cls}>last run: {text}</a>'


def _bar(summary: Mapping) -> str:
    ps = summary["platforms"]
    order = platform_order(summary)
    g1 = '<a href="#tab=overview" data-tab="overview" data-title="Overview">Overview</a>'
    g1 += "".join(
        f'<a href="#tab={e(p)}" data-tab="{e(p)}" data-title="{e(ps[p]["title"])}">'
        f'{e(ps[p]["title"])} <span class="n">{ps[p]["packages"]:,}</span></a>'
        for p in order
    )
    g2 = "".join(
        f'<a href="#tab={v}" data-tab="{v}" data-title="{t}">{t}</a>'
        for v, t in _MORE_VIEWS.items()
    )
    jump = " ".join(
        f'<a href="#sec-{e(p)}">{e(ps[p]["title"])}</a>' for p in order
    ) + ' <a href="#how">How to read</a>'
    return (
        '<div class="bar"><div class="wrap">'
        f'<nav class="tabs jsonly" aria-label="Views"><div class="g1">{g1}</div>'
        f'<span class="sep"></span><div class="g2" id="more-views">{g2}</div>'
        '<button type="button" class="more-btn" aria-expanded="false" '
        'aria-controls="more-views" aria-label="More views">⋯</button></nav>'
        f'<nav class="jump" data-view="all" aria-label="Jump to">{jump}</nav>'
        "</div></div>"
    )


def render_page(
    summary: Mapping[str, Any],
    *,
    title: str = DFLT_TITLE,
    default_view: str = DFLT_VIEW,
) -> str:
    """The report page for a :func:`~pkgreach.analyze.summarize` result.

    ``default_view``: what a bare URL opens: ``"overview"``, a platform's
    name (``"pypi"``), ``"all"``, ``"projects"`` or ``"movers"``.
    """
    valid = views_of(summary)
    if default_view not in valid:
        raise ValueError(
            f"default_view={default_view!r} is not a view of this report; "
            f"choose one of {valid}"
        )
    clash = set(summary["platforms"]) & set(FIXED_VIEWS)
    if clash:
        raise ValueError(f"platform names clash with view names: {sorted(clash)}")
    ps = summary["platforms"]
    sections = "".join(
        platform_section(p, rows_of(summary, p), ps[p]) for p in platform_order(summary)
    )
    att = summary.get("attribution", {})
    return f"""<!doctype html>
<html lang="en" data-default="{e(default_view)}" data-title="{e(title)}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{e(title)}</title><script>document.documentElement.classList.add('js')</script>
<style>{CSS}</style></head>
<body><div class="wrap" id="top"><header class="top"><h1>{e(title)}</h1>
<p class="muted small">As of {e(summary["as_of"])}{_status(summary)} ·
<a href="summary.json">summary.json</a> · made with
<a href="https://github.com/thorwhalen/pkgreach">pkgreach</a></p></header></div>
{_bar(summary)}
<main class="wrap">
{overview(summary)}
{sections}
{projects(summary)}
{movers(summary)}
<section data-view="overview all">{HOW_TO_READ}</section>
</main>
<footer class="wrap muted small"><p>Downloads: {e(att.get("downloads", ""))}.
Dependents: {link("https://ecosyste.ms", "ecosyste.ms")}, licensed
{link("https://creativecommons.org/licenses/by-sa/4.0/", "CC BY-SA 4.0")},
aggregated here. Stars and forks: GitHub, public repositories only.</p></footer>
<script>{JS}</script></body></html>
"""
