"""The report: a static site (one ``index.html`` plus ``summary.json``).

:func:`build_site` reads the history, summarizes it (the ``analyze=`` seam)
and writes the page into ``out``, any
``MutableMapping[str, str]``: a folder by default, which any static host
serves (GitHub Pages, your own server, an S3 bucket through a ``dol`` store).

Nothing here knows a platform by name: titles, the kind of table (daily
downloads or snapshot metrics) and the headline metrics come from the
summary, which takes them from each :class:`~pkgreach.platforms.Platform`.

The page is generated, not an app: the data is baked in, nothing is fetched at
view time, and the only script sorts tables. Every string from a registry is
escaped, and only ``http(s)`` links are emitted.
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any

from pkgreach.analyze import summarize
from pkgreach.tables import SUMMARY_KEY

Summary = dict[str, Any]
DFLT_TITLE = "Package reach"


def _e(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _link(url: str, text: str) -> str:
    if url.startswith(("https://", "http://")):
        return f'<a href="{_e(url)}">{_e(text)}</a>'
    return _e(text)


def _num(n: Any) -> str:
    if n is None or n == "":
        return "–"
    n = int(n)
    if abs(n) >= 10_000:
        return f"{n / 1000:,.0f}k"
    return f"{n:,}"


def _pct(x: float | None) -> str:
    if x is None:
        return '<span class="muted">–</span>'
    cls = "up" if x > 0 else "down" if x < 0 else "muted"
    return f'<span class="{cls}">{x:+.0%}</span>'


def _times(x: float | None) -> str:
    if x is None:
        return "–"
    return f"{x:,.0f}×" if x >= 10 else f"{x:g}×"


def _signed(n: int | None) -> str:
    if not n:
        return ""
    cls = "up" if n > 0 else "down"
    return f' <span class="{cls} small">{n:+,}</span>'


def _spark(values: list[int], *, w: int = 120, h: int = 28) -> str:
    if not values or not any(values):
        return '<span class="muted small">no downloads</span>'
    top = max(values)
    step = w / max(1, len(values) - 1)
    pts = " ".join(
        f"{i * step:.1f},{h - 2 - (v / top) * (h - 4):.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="weekly downloads, last {len(values)} weeks">'
        f'<polyline points="{pts}" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linejoin="round"/></svg>'
    )


def _metric(row: Mapping, name: str) -> dict:
    return row["metrics"].get(name, {})


def _label(metric: str) -> str:
    return metric.replace("_", " ")


def _errors_note(summary: Mapping) -> str:
    n = summary.get("last_run_errors")
    if not n:
        return ""
    return f' · <span class="down">last run: {n} errors (see last_run.json)</span>'


def _card(p: Mapping) -> str:
    if p["kind"] == "snapshot":
        t, head = p["metric_totals"], p["headline"]
        rest = " · ".join(f"{_num(t.get(m))} {_label(m)}" for m in head[1:])
        body = (
            f'<div class="big">{_num(t.get(head[0]) if head else None)}</div>'
            f'<div class="small">{_label(head[0]) if head else ""} across '
            f"{p['packages']} {'· ' + rest if rest else ''}</div>"
        )
    else:
        prev = p["downloads_prev_30d"]
        growth = p["downloads_30d"] / prev - 1 if prev else None
        deps = p["metric_totals"].get("dependent_packages")
        body = (
            f'<div class="big">{_num(p["downloads_30d"])}</div>'
            f'<div class="small">downloads, last 30 days {_pct(growth)}</div>'
            f'<div class="small">{p["packages"]} packages · '
            f"{_num(deps)} dependent packages · noise floor "
            f"{_num(p['noise_floor_30d'])}/30d</div>"
        )
    return f'<section class="card"><h3>{_e(p["title"])}</h3>{body}</section>'


def _registry_table(rows: list[Mapping]) -> str:
    rows = sorted(rows, key=lambda r: -r["downloads"]["30d"])
    head = (
        "<tr><th data-sort>package</th><th data-sort=num>30d</th>"
        "<th data-sort=num>vs prior</th><th data-sort=num title='30-day downloads "
        "over the noise floor'>× floor</th><th data-sort=num title='dependent "
        "packages / repositories'>dependents</th><th>26 weeks</th></tr>"
    )
    body = []
    for r in rows:
        dp = _metric(r, "dependent_packages").get("value")
        dr = _metric(r, "dependent_repos").get("value")
        deps = f"{_num(dp)} / {_num(dr)}" if dp is not None or dr is not None else "–"
        xf = r.get("x_floor")
        body.append(
            f"<tr><td>{_link(r['url'], r['package'])}</td>"
            f'<td data-v="{r["downloads"]["30d"]}">{_num(r["downloads"]["30d"])}</td>'
            f'<td data-v="{r["growth_30d"] if r["growth_30d"] is not None else ""}">'
            f"{_pct(r['growth_30d'])}</td>"
            f'<td data-v="{xf if xf is not None else ""}">'
            f"{_times(xf)}</td>"
            f'<td data-v="{(dp or 0) * 1_000_000 + (dr or 0)}">{deps}</td>'
            f"<td>{_spark(r['weekly'])}</td></tr>"
        )
    return f'<table class="sortable"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table>'


def _snapshot_table(rows: list[Mapping], headline: list[str]) -> str:
    first = headline[0] if headline else ""
    rows = sorted(rows, key=lambda r: -(_metric(r, first).get("value") or 0))
    head = "<tr><th data-sort>name</th>" + "".join(
        f"<th data-sort=num>{_e(_label(m))}</th>" for m in headline
    )
    body = []
    for r in rows:
        cells = []
        for m in headline:
            d = _metric(r, m)
            cells.append(
                f'<td data-v="{d.get("value", "")}">{_num(d.get("value"))}'
                f"{_signed(d.get('change_30d'))}</td>"
            )
        body.append(
            f"<tr><td>{_link(r['url'], r['package'])}</td>{''.join(cells)}</tr>"
        )
    return (
        f'<table class="sortable"><thead>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
    )


_CSS = """
:root{--bg:#fbfbfa;--fg:#1d1d1f;--muted:#6e6e73;--line:#e3e3e0;--card:#fff;
--accent:#2f6fde;--up:#1f8a4c;--down:#c0392b}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#141416;
--fg:#ececee;--muted:#9a9aa1;--line:#2c2c30;--card:#1c1c1f;--accent:#7aa7ff;
--up:#5cc98a;--down:#ff7b6b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:.2em 0}h2{margin:1.6em 0 .4em;font-size:1.15rem}
h3{margin:0 0 .3em;font-size:1rem;color:var(--muted);font-weight:600}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.muted{color:var(--muted)}.small{font-size:.85rem}.up{color:var(--up)}.down{color:var(--down)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(210px,100%),1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.big{font-size:1.7rem;font-weight:650;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--card)}
th{font-size:.8rem;color:var(--muted);font-weight:600}th[data-sort]{cursor:pointer}
th[aria-sort=descending]::after{content:" ▾"}th[aria-sort=ascending]::after{content:" ▴"}
.spark{color:var(--accent);vertical-align:middle}
details{margin:1.5em 0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
summary{cursor:pointer;font-weight:600}
"""

_JS = """
document.querySelectorAll('table.sortable th[data-sort]').forEach((th,i)=>{
th.addEventListener('click',()=>{const t=th.closest('table'),b=t.tBodies[0];
const col=[...th.parentNode.children].indexOf(th),num=th.dataset.sort==='num';
const dir=th.getAttribute('aria-sort')==='descending'?1:-1;
t.querySelectorAll('th').forEach(h=>h.removeAttribute('aria-sort'));
th.setAttribute('aria-sort',dir<0?'descending':'ascending');
const val=r=>{const c=r.children[col];return num?parseFloat(c.dataset.v||'-1e18'):c.textContent.toLowerCase()};
[...b.rows].sort((x,y)=>{const a=val(x),z=val(y);return (a>z?1:a<z?-1:0)*dir}).forEach(r=>b.appendChild(r))})});
"""

_HOW_TO_READ = """
<details><summary>How to read these numbers</summary>
<p><b>Downloads are mostly not people.</b> Mirrors, CI pipelines, security
scanners and bots fetch every release of every package, so a package nobody
uses still gets a steady trickle. The <b>noise floor</b> is the 25th percentile
of 30-day downloads among the packages followed here that were downloaded at all; <b>× floor</b> says how
far above it a package is. A package near 1× is probably only seen by robots.</p>
<p><b>The strongest signs of real use</b> are the ones a robot does not create:
<b>dependents</b> (other packages and repositories that declare it, from
ecosyste.ms), stars and forks, and issues opened by people other than you.
Growth over the prior 30 days matters more than the level.</p>
<p>PyPI counts exclude known mirrors (pypistats.org's <i>without_mirrors</i>).
Registries keep only a few months of daily counts, so this history starts at
each package's first collection.</p></details>
"""


def render_html(summary: Summary, *, title: str = DFLT_TITLE) -> str:
    """The report page for a :func:`~pkgreach.analyze.summarize` result."""
    platforms = summary["platforms"]
    # daily-download platforms first, by downloads; then snapshot ones
    order = sorted(
        platforms,
        key=lambda n: (platforms[n]["kind"] != "daily", -platforms[n]["downloads_30d"]),
    )
    cards = "".join(_card(platforms[p]) for p in order)
    sections = []
    for p in order:
        meta = platforms[p]
        rows = [r for r in summary["packages"] if r["platform"] == p]
        if meta["kind"] == "snapshot":
            table = _snapshot_table(rows, meta["headline"])
        else:
            table = _registry_table(rows)
        sections.append(
            f"<h2>{_e(meta['title'])} "
            f'<span class="muted small">{len(rows)}</span></h2>'
            f'<div class="scroll">{table}</div>'
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><style>{_CSS}</style></head>
<body><main>
<h1>{_e(title)}</h1>
<p class="muted small">As of {_e(summary["as_of"])} · made with
<a href="https://github.com/thorwhalen/pkgreach">pkgreach</a> ·
<a href="summary.json">summary.json</a>{_errors_note(summary)}</p>
<div class="cards">{cards}</div>
{_HOW_TO_READ}
{"".join(sections)}
<p class="muted small">Downloads: pypistats.org, api.npmjs.org, crates.io.
Dependents: <a href="https://ecosyste.ms">ecosyste.ms</a>, licensed
<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>,
aggregated here. Stars and forks: GitHub, public repositories only.</p>
</main><script>{_JS}</script></body></html>
"""


def build_site(
    store: MutableMapping,
    out: MutableMapping,
    *,
    analyze: Callable[[MutableMapping], Summary] = summarize,
    title: str = DFLT_TITLE,
) -> Summary:
    """Summarize the history in ``store`` and write the site into ``out``.

    ``analyze`` is the seam for another summary (it must return the shape of
    :func:`~pkgreach.analyze.summarize`, which ``summary.json`` documents).
    """
    # seam candidate: render= (another page from the same summary), once a
    # second renderer exists
    summary = analyze(store)
    out[SUMMARY_KEY] = json.dumps(summary, indent=1) + "\n"
    out["index.html"] = render_html(summary, title=title)
    return summary
