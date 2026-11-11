"""The page's views, each a function from the summary to an HTML fragment.

A view never branches on a platform's name: what a platform is (daily
downloads or snapshot metrics), what it calls its packages and which metrics
it headlines all come from ``summary["platforms"][name]``.

Tables are rendered complete and in their default order (signal first, noise
last), so the page reads without JavaScript; the script only filters, sorts
and shortens them (see :mod:`pkgreach.render.assets`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pkgreach.render.fmt import (
    e,
    full,
    label,
    link,
    metric,
    num,
    pct,
    plural,
    signed,
    spark,
    times,
    units,
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


def _signal(meta: Mapping) -> float:
    return meta.get("signal_x_floor") or 3.0


def is_quiet(row: Row, meta: Mapping) -> bool:
    """Noise: under the signal threshold (daily), or every headline at zero."""
    if meta["kind"] == "snapshot":
        return not any(metric(row, m) for m in meta["headline"])
    xf = row.get("x_floor")
    return xf is None or xf < _signal(meta)


def is_steady(row: Row, meta: Mapping) -> bool:
    """Above the signal threshold in both 30-day windows: its change means something."""
    return (
        not is_quiet(row, meta)
        and not row.get("prev_low_base")
        and row.get("growth_30d") is not None
    )


def _gain(r: Row) -> int:
    return r["downloads"]["30d"] - r["downloads_prev_30d"]


def _daily(summary: Summary) -> list[str]:
    return [p for p in platform_order(summary) if summary["platforms"][p]["kind"] == "daily"]


def _badge(meta: Mapping) -> str:
    return f'<span class="badge">{e(meta["title"])}</span>'


def _tab(view: str, text: str, **params: str) -> str:
    """A link to a view: ``#tab=<view>&...`` in the page's one URL spelling."""
    extra = "".join(f"&amp;{k}={e(v)}" for k, v in params.items())
    return f'<a class="see" href="#tab={e(view)}{extra}">{text}</a>'


# --------------------------------------------------------------------------- #
# Change, as a cell


def change_cell(r: Row) -> str:
    """Growth relative to the platform's median, or why there is none."""
    if not r.get("has_downloads"):
        return '<td class="num" data-v="">–</td>'
    if not r.get("prev_covered", True) or (
        r["downloads_prev_30d"] == 0 and r["downloads"]["30d"]
    ):
        return '<td class="num" data-v=""><span class="tag">new</span></td>'
    if r.get("prev_low_base"):
        return '<td class="num" data-v=""><span class="tag">low base</span></td>'
    g = r.get("growth_vs_median_30d")
    return f'<td class="num" data-v="{"" if g is None else g}">{pct(g)}</td>'


def _chg_label(meta: Mapping) -> str:
    return "vs median"


# --------------------------------------------------------------------------- #
# Platform tables


def _th(key: str, text: str, *, cls: str = "") -> str:
    return (
        f'<th class="{cls}" data-k="{e(key)}" aria-sort="none">'
        f'<button type="button" aria-pressed="false">{text}</button></th>'
    )


def _name_cell(r: Row, chip: str = "") -> str:
    name = str(r["package"])
    return (
        f'<td class="name" data-s="{e(name.lower())}">'
        f"{link(r['url'], name, cls='nm')}{chip}</td>"
    )


def _dep_metrics(rows: list[Row]) -> list[str]:
    return [m for m in DEPENDENT_METRICS if any(metric(r, m) for r in rows)]


def _chip(r: Row, deps: list[str]) -> str:
    parts = [
        units(int(v), _short(m)).replace(f"{int(v):,}", num(v), 1)
        for m in deps
        if (v := metric(r, m))
    ]
    return f'<span class="chip">used by {" · ".join(parts)}</span>' if parts else ""


def _short(dep_metric: str) -> str:
    """``dependent_packages`` -> ``pkgs``, ``dependent_repos`` -> ``repos``."""
    word = label(dep_metric).removeprefix("dependent ")
    return {"packages": "pkgs"}.get(word, word)


def _q(r: Row) -> str:
    return e(f"{r['package']} {r.get('description') or ''}".lower())


def daily_table(rows: list[Row], meta: Mapping) -> tuple[str, list[tuple[str, str]]]:
    """The table of a daily-download platform, and its sort options."""
    deps = _dep_metrics(rows)
    rows = sorted(
        rows, key=lambda r: (is_quiet(r, meta), -r["downloads"]["30d"], r["package"])
    )
    head = (
        _th("name", "package", cls="name")
        + _th("30d", "30 days", cls="num")
        + _th("chg", _chg_label(meta), cls="num")
        + _th("x", "× floor", cls="num c-x")
        + "".join(
            _th(m, label(m).replace("dependent ", "dependent<br>"), cls="num c-dep")
            for m in deps
        )
        + '<th class="c-spark">26 weeks</th>'
    )
    body = []
    for i, r in enumerate(rows):
        xf = r.get("x_floor")
        quiet = " quiet" if is_quiet(r, meta) else ""
        cells = [
            _name_cell(r, _chip(r, deps)),
            f'<td class="num" data-v="{r["downloads"]["30d"]}">'
            f"{num(r['downloads']['30d'])}</td>",
            change_cell(r),
            f'<td class="num c-x" data-v="{"" if xf is None else xf}">'
            f"{times(xf)}</td>",
            *(
                f'<td class="num c-dep" data-v="{metric(r, m) or 0}">'
                f"{num(metric(r, m) or 0) if metric(r, m) else ''}</td>"
                for m in deps
            ),
            f'<td class="c-spark">{spark(r["weekly"])}</td>',
        ]
        body.append(
            f'<tr class="r{quiet}" data-i="{i}" data-q="{_q(r)}">{"".join(cells)}</tr>'
        )
    sorts = [
        ("-30d", "Downloads"),
        ("-chg", "Growth vs median"),
        ("-x", "× floor"),
        *((f"-{m}", label(m).capitalize()) for m in deps),
        ("name", "Name"),
    ]
    return _table(head, body), sorts


def snapshot_table(rows: list[Row], meta: Mapping) -> tuple[str, list[tuple[str, str]]]:
    """The table of a snapshot platform: its headline metrics, with 30-day changes."""
    head_ms = meta["headline"]
    first = head_ms[0] if head_ms else None
    rows = sorted(
        rows,
        key=lambda r: (is_quiet(r, meta), -(metric(r, first) or 0), r["package"]),
    )
    head = _th("name", "name", cls="name") + "".join(
        _th(m, e(label(m)), cls="num") for m in head_ms
    )
    body = []
    for i, r in enumerate(rows):
        cells = [_name_cell(r)]
        for m in head_ms:
            d = r["metrics"].get(m, {})
            v = d.get("value")
            cells.append(
                f'<td class="num" data-v="{"" if v is None else v}">{num(v)}'
                f"{signed(d.get('change_30d'))}</td>"
            )
        quiet = " quiet" if is_quiet(r, meta) else ""
        body.append(
            f'<tr class="r{quiet}" data-i="{i}" data-q="{_q(r)}">{"".join(cells)}</tr>'
        )
    sorts = [(f"-{m}", label(m).capitalize()) for m in head_ms] + [("name", "Name")]
    return _table(head, body), sorts


def _table(head: str, body: list[str]) -> str:
    return (
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def _noise_tip(name: str, meta: Mapping) -> str:
    if meta["kind"] == "snapshot":
        return (
            f"{e(meta['unit']).capitalize()} with no "
            f"{e(' and no '.join(label(m) for m in meta['headline']))} are dimmed "
            "and listed last."
        )
    floor, sx = meta.get("noise_floor_30d"), _signal(meta)
    med = meta.get("median_growth_30d")
    return (
        f"The noise floor is {full(floor)} downloads in 30 days: what the least-used "
        f"{e(meta['unit'])} here get from mirrors, CI and bots. Rows under {sx:g}× "
        "it are noise: dimmed and listed last. "
        "<b>vs median</b> is a package's change on the prior 30 days, relative to "
        "the median package's"
        + (f" ({med:+.0%})" if med is not None else "")
        + ", so a platform-wide jump in robot traffic cancels out. "
        f"<b>low base</b>: under {sx:g}× the floor in the prior 30 days, so its "
        "percentage means little. <b>new</b>: not followed for the whole prior "
        "window."
    )


def platform_section(name: str, rows: list[Row], meta: Mapping) -> str:
    """One platform: controls, then its table (its tab, and its part of All)."""
    if meta["kind"] == "snapshot":
        table, sorts = snapshot_table(rows, meta)
        dflt = f"-{meta['headline'][0]}" if meta["headline"] else "name"
        hide = "Hide empty"
    else:
        table, sorts = daily_table(rows, meta)
        dflt, hide = "-30d", "Hide noise"
    n_quiet = sum(is_quiet(r, meta) for r in rows)
    opts = "".join(f'<option value="{e(v)}">{e(t)}</option>' for v, t in sorts)
    title, sid = e(meta["title"]), e(name)
    noise = (
        f'<button type="button" class="btn noise" aria-pressed="true">'
        f"{hide} ({n_quiet})</button>"
        if n_quiet
        else ""
    )
    return f"""
<section class="tbl" data-view="{sid} all" id="sec-{sid}" data-sort="{e(dflt)}"
 data-limit="{DFLT_ROW_LIMIT}">
<h2>{title} <span class="muted small">{units(len(rows), e(meta["unit"]))}</span>
<a class="totop small" href="#top">↑ top</a></h2>
<div class="controls jsonly">
<input type="search" class="q" placeholder="Search name or description"
 aria-label="Search {title}" autocomplete="off">
<label class="sortsel">Sort <select class="sort">{opts}</select></label>
{noise}<button type="button" class="tip" aria-expanded="false"
 aria-controls="tip-{sid}" aria-label="What is noise?">i</button>
<p class="tipbox small" id="tip-{sid}" hidden>{_noise_tip(name, meta)}</p>
</div>
{table}
<p class="rowsnote jsonly"><button type="button" class="btn more" hidden></button>
<span class="muted small count" role="status"></span></p>
</section>"""


# --------------------------------------------------------------------------- #
# Overview


def card(name: str, p: Mapping) -> str:
    """A platform's card: its headline number and what qualifies it."""
    t = p["metric_totals"]
    if p["kind"] == "snapshot":
        head = p["headline"]
        big = num(t.get(head[0])) if head else "–"
        rest = [f"{num(t.get(m))} {label(m)}" for m in head[1:] if t.get(m)]
        lines = [
            f"{e(label(head[0]) if head else '')} across "
            f"{units(p['packages'], e(p['unit']))}",
            " · ".join(rest),
        ]
    else:
        big = num(p["downloads_30d"])
        g, med = p.get("growth_30d"), p.get("median_growth_30d")
        deps = [
            units(int(t[m]), label(m).removeprefix("dependent "))
            for m in DEPENDENT_METRICS
            if t.get(m)
        ]
        floor = p.get("noise_floor_30d")
        lines = [
            "downloads in 30 days"
            + (f" {pct(g)}" if g is not None else ""),
            f"median package {pct(med)}" if med is not None else "",
            units(p["packages"], e(p["unit"]))
            + (f" · noise floor {full(floor)}" if floor else ""),
            f"used by {' · '.join(deps)}" if deps else "",
        ]
    body = "".join(f'<div class="small">{x}</div>' for x in lines if x)
    return (
        f'<a class="card" href="#tab={e(name)}"><h3>{e(p["title"])}</h3>'
        f'<div class="big">{big}</div>{body}</a>'
    )


def _mini(rows: list[tuple[Mapping, Row]], value) -> str:
    """A compact list: badge, name, a value, sparkline."""
    if not rows:
        return '<p class="muted small">None yet.</p>'
    items = "".join(
        f"<tr><td>{_badge(meta)}</td>{_name_cell(r)}"
        f'<td class="num">{value(r)}</td>'
        f'<td class="c-spark">{spark(r.get("weekly") or [])}</td></tr>'
        for meta, r in rows
    )
    return f'<div class="scroll"><table class="mini"><tbody>{items}</tbody></table></div>'


def _see_all(summary: Summary, platforms: list[str], **params: str) -> str:
    ps = summary["platforms"]
    links = " · ".join(_tab(p, e(ps[p]["title"]), **params) for p in platforms)
    return f'<p class="small">See all in {links} →</p>' if links else ""


def overview(summary: Summary) -> str:
    ps = summary["platforms"]
    order = platform_order(summary)
    daily = _daily(summary)
    cards = "".join(card(p, ps[p]) for p in order)
    pairs = [(ps[p], r) for p in daily for r in rows_of(summary, p)]

    used = sorted(
        (x for x in pairs if x[1].get("x_floor")), key=lambda x: -x[1]["x_floor"]
    )[:TOP_USED]
    blocks = [
        "<h2>Most used</h2>"
        '<p class="muted small">Ranked by how far above its platform\'s noise '
        "floor a package is, which compares across platforms.</p>"
        + _mini(used, lambda r: f"{num(r['downloads']['30d'])} <span "
                f'class="muted small">{times(r["x_floor"])}</span>')
        + _see_all(summary, daily)
    ]

    steady = [x for x in pairs if is_steady(x[1], x[0])]
    up = sorted((x for x in steady if _gain(x[1]) > 0), key=lambda x: -_gain(x[1]))
    down = sorted((x for x in steady if _gain(x[1]) < 0), key=lambda x: _gain(x[1]))

    def move(r):
        return f'{signed(_gain(r)).strip()}'

    blocks.append(
        '<h2>Movers</h2><p class="muted small">Largest change in 30-day downloads, '
        "among packages above the noise in both windows.</p>"
        '<div class="two"><div><h3>Up</h3>'
        + _mini(up[:TOP_MOVERS], move)
        + "</div><div><h3>Down</h3>"
        + _mini(down[:TOP_MOVERS], move)
        + "</div></div>"
        + f'<p class="small">{_tab("movers", "See all movers")} →</p>'
    )

    dep_m = DEPENDENT_METRICS[0]
    depended = sorted(
        (x for x in pairs if metric(x[1], dep_m)),
        key=lambda x: -(metric(x[1], dep_m) or 0),
    )
    if depended:
        blocks.append(
            f"<h2>Depended on</h2><p class=\"muted small\">Packages other packages "
            f"declare as a dependency ({len(depended)}), the sign of use a robot "
            "does not create.</p>"
            + _mini(
                depended[:TOP_DEPENDED],
                lambda r: f"{num(metric(r, dep_m))} <span class=\"muted small\">"
                f"{label(dep_m).removeprefix('dependent ')}</span>",
            )
            + _see_all(
                summary,
                [p for p in daily if any(metric(r, dep_m) for m, r in pairs if m is ps[p])],
                sort=f"-{dep_m}",
            )
        )

    for p in order:
        meta = ps[p]
        if meta["kind"] != "snapshot" or not meta["headline"]:
            continue
        m = meta["headline"][0]
        top = sorted(
            (r for r in rows_of(summary, p) if metric(r, m)),
            key=lambda r: -(metric(r, m) or 0),
        )[:TOP_SNAPSHOT]
        items = "".join(
            f"<tr>{_name_cell(r)}<td class=\"num\">{num(metric(r, m))} "
            f'<span class="muted small">{e(label(m))}</span></td></tr>'
            for r in top
        )
        blocks.append(
            f"<h2>Top {e(meta['title'])} {e(meta['unit'])} by {e(label(m))}</h2>"
            f'<div class="scroll"><table class="mini"><tbody>{items}</tbody></table></div>'
            + _see_all(summary, [p])
        )
    return (
        f'<section data-view="overview" class="jsonly"><div class="cards">{cards}</div>'
        + "".join(f'<div class="block">{b}</div>' for b in blocks)
        + "</section>"
    )


# --------------------------------------------------------------------------- #
# Projects


def _repo_key(url: str) -> str:
    u = str(url).strip().lower().rstrip("/").removesuffix(".git").rstrip("/")
    u = u.replace("http://", "https://", 1).replace("://www.", "://", 1)
    return u if u.startswith("https://") else ""


def projects(summary: Summary) -> str:
    """One row per project: the packages that share a repository, joined."""
    ps = summary["platforms"]
    order = platform_order(summary)
    groups: dict[str, dict] = {}
    for p in order:
        for r in rows_of(summary, p):
            key = _repo_key(r.get("repository") or "")
            if not key and ps[p]["kind"] == "snapshot":
                key = _repo_key(r.get("url") or "")
            key = key or f"{p}:{r['package']}"
            g = groups.setdefault(key, {"rows": {}, "repo": ""})
            g["rows"].setdefault(p, []).append(r)
            if key.startswith("https://"):
                g["repo"] = r.get("repository") or r.get("url")
    daily = [p for p in _daily(summary) if any(p in g["rows"] for g in groups.values())]
    snaps = [p for p in order if ps[p]["kind"] == "snapshot"]
    dep_m = DEPENDENT_METRICS[0]

    def tot(g, p, f):
        return sum(f(r) for r in g["rows"].get(p, []))

    def is_empty(g):
        return not any(p in g["rows"] for p in daily) and not any(
            tot(g, p, lambda r, m=ps[p]["headline"][0]: metric(r, m) or 0)
            for p in snaps
            if ps[p]["headline"]
        )

    full_rows, empty = [], []
    for key, g in groups.items():
        (empty if is_empty(g) else full_rows).append((key, g))

    def score(item):
        g = item[1]
        xf = max((r.get("x_floor") or 0 for p in daily for r in g["rows"].get(p, [])), default=0)
        stars = sum(
            tot(g, p, lambda r, m=ps[p]["headline"][0]: metric(r, m) or 0)
            for p in snaps
            if ps[p]["headline"]
        )
        return (-xf, -stars, item[0])

    full_rows.sort(key=score)
    head = _th("name", "project", cls="name")
    # on a phone: the first platform's downloads, dependents, the first headline
    head += "".join(
        _th(f"dl-{p}", f"{e(ps[p]['title'])} 30d", cls="num" + (" c-x" if i else ""))
        for i, p in enumerate(daily)
    )
    head += _th("deps", "dependents", cls="num")
    for p in snaps:
        head += "".join(
            _th(f"{p}-{m}", e(label(m)), cls="num" + ("" if i == 0 else " c-x"))
            for i, m in enumerate(ps[p]["headline"])
        )
    body = []
    for i, (key, g) in enumerate(full_rows):
        name = key.split("/", 3)[-1] if key.startswith("https://") else key.split(":", 1)[1]
        pk = [
            f"{e(ps[p]['title'])}: {', '.join(e(r['package']) for r in g['rows'][p])}"
            for p in daily
            if p in g["rows"]
        ]
        sub = f'<span class="chip keep">{" · ".join(pk)}</span>' if pk else ""
        url = g["repo"] or next(iter(g["rows"].values()))[0].get("url", "")
        cells = [
            f'<td class="name" data-s="{e(name.lower())}">{link(url, name, cls="nm", wbr=True)}{sub}</td>'
        ]
        for j, p in enumerate(daily):
            v = tot(g, p, lambda r: r["downloads"]["30d"]) if p in g["rows"] else None
            cells.append(
                f'<td class="num{" c-x" if j else ""}" data-v="{"" if v is None else v}">'
                f"{'' if v is None else num(v)}</td>"
            )
        deps = sum(tot(g, p, lambda r: metric(r, dep_m) or 0) for p in daily)
        cells.append(f'<td class="num" data-v="{deps}">{num(deps) if deps else ""}</td>')
        for p in snaps:
            for j, m in enumerate(ps[p]["headline"]):
                v = tot(g, p, lambda r, m=m: metric(r, m) or 0) if p in g["rows"] else None
                cells.append(
                    f'<td class="num{"" if j == 0 else " c-x"}" '
                    f'data-v="{"" if v is None else v}">{"" if v is None else num(v)}</td>'
                )
        q = e(f"{name} {' '.join(str(r['package']) for rs in g['rows'].values() for r in rs)}".lower())
        body.append(f'<tr class="r" data-i="{i}" data-q="{q}">{"".join(cells)}</tr>')

    note = ""
    if empty:
        links = ", ".join(
            link(g["repo"] or "", k.split("/", 3)[-1] if k.startswith("https://") else k)
            for k, g in sorted(empty)
        )
        what = " and no ".join(
            label(ps[p]["headline"][0]) for p in snaps if ps[p]["headline"]
        )
        unit_word = "/".join(sorted({ps[p]["unit"] for p in snaps})) or "projects"
        n_snap = sum(len(rows_of(summary, p)) for p in snaps)
        note = (
            f'<details class="small"><summary>{units(len(empty), e(unit_word))}'
            f" with no package and no {e(what)} (of {n_snap:,})</summary>"
            f"<p>{links}</p></details>"
        )
    return f"""
<section class="tbl" data-view="projects" data-sort="" data-limit="{DFLT_ROW_LIMIT}">
<h2>Projects <span class="muted small">{plural(len(full_rows), "project")}</span></h2>
<p class="muted small">Packages joined to the repository they declare: what one
project reaches across platforms.</p>
<div class="controls"><input type="search" class="q" placeholder="Search project or package"
 aria-label="Search projects" autocomplete="off"></div>
{_table(head, body)}
<p class="rowsnote"><button type="button" class="btn more" hidden></button>
<span class="muted small count" role="status"></span></p>
{note}
</section>"""


# --------------------------------------------------------------------------- #
# Movers


def _mover_table(rows: list[Row]) -> str:
    if not rows:
        return '<p class="muted small">None.</p>'
    body = "".join(
        f"<tr>{_name_cell(r)}"
        f'<td class="num">{full(r["downloads_prev_30d"])} → '
        f"<b>{full(r['downloads']['30d'])}</b></td>"
        f'<td class="num">{pct(r["growth_30d"])}</td>'
        f'<td class="num c-x">{pct(r.get("growth_vs_median_30d"))}</td></tr>'
        for r in rows
    )
    head = (
        '<tr><th class="name">package</th><th class="num">prior 30 → last 30</th>'
        '<th class="num">change</th><th class="num c-x">vs median</th></tr>'
    )
    return f'<div class="scroll"><table class="mini"><thead>{head}</thead><tbody>{body}</tbody></table></div>'


def movers(summary: Summary) -> str:
    """Per daily platform, every steady package that gained or lost, ranked."""
    ps = summary["platforms"]
    parts = []
    for p in _daily(summary):
        meta = ps[p]
        steady = [r for r in rows_of(summary, p) if is_steady(r, meta)]
        up = sorted((r for r in steady if _gain(r) > 0), key=lambda r: -_gain(r))
        down = sorted((r for r in steady if _gain(r) < 0), key=_gain)
        parts.append(
            f"<h2>{e(meta['title'])}</h2>"
            f'<div class="two"><div><h3>Gainers ({len(up)})</h3>{_mover_table(up)}</div>'
            f"<div><h3>Decliners ({len(down)})</h3>{_mover_table(down)}</div></div>"
        )
    return (
        '<section data-view="movers" class="jsonly">'
        '<p class="muted small">Packages above the noise in both 30-day windows, '
        "by how many downloads they gained or lost. A package under the noise in "
        "either window is left out: its percentages are mostly robots.</p>"
        + "".join(parts)
        + "</section>"
    )
