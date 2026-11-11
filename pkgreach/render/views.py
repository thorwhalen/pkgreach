"""The views across platforms: Overview, Projects and Movers.

Each is a function from the summary to an HTML fragment; the per-platform
tabs are in :mod:`pkgreach.render.platform`.
"""

from __future__ import annotations

from collections.abc import Mapping

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
    tab_href,
    times,
    unit_of,
    units,
)
from pkgreach.render.read import (
    DEPENDENT_METRICS,
    DFLT_ROW_LIMIT,
    TOP_DEPENDED,
    TOP_MOVERS,
    TOP_SNAPSHOT,
    TOP_USED,
    Row,
    Summary,
    badge,
    daily_platforms,
    gain,
    is_steady,
    name_cell,
    platform_order,
    rows_of,
    tab_link,
    table_html,
    th,
)

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
            f"{units(p['packages'], unit_of(p))}",
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
            "downloads in 30 days" + (f" {pct(g)}" if g is not None else ""),
            f"median package {pct(med)}" if med is not None else "",
            units(p["packages"], unit_of(p))
            + (f" · noise floor {full(floor)}" if floor else ""),
            f"used by {' · '.join(deps)}" if deps else "",
        ]
    body = "".join(f'<div class="small">{x}</div>' for x in lines if x)
    return (
        f'<a class="card" href="{tab_href(name)}"><h3>{e(p["title"])}</h3>'
        f'<div class="big">{big}</div>{body}</a>'
    )


def _mini(rows: list[tuple[Mapping, Row]], value) -> str:
    """A compact list: badge, name, a value, sparkline."""
    if not rows:
        return '<p class="muted small">None yet.</p>'
    items = "".join(
        f"<tr><td>{badge(meta)}</td>{name_cell(r)}"
        f'<td class="num">{value(r)}</td>'
        f'<td class="c-spark">{spark(r.get("weekly") or [])}</td></tr>'
        for meta, r in rows
    )
    return (
        f'<div class="scroll"><table class="mini"><tbody>{items}</tbody></table></div>'
    )


def _see_all(summary: Summary, platforms: list[str], **params: str) -> str:
    ps = summary["platforms"]
    links = " · ".join(tab_link(p, e(ps[p]["title"]), **params) for p in platforms)
    return f'<p class="small">See all in {links} →</p>' if links else ""


def overview(summary: Summary) -> str:
    ps = summary["platforms"]
    order = platform_order(summary)
    daily = daily_platforms(summary)
    cards = "".join(card(p, ps[p]) for p in order)
    pairs = [(ps[p], r) for p in daily for r in rows_of(summary, p)]

    used = sorted(
        (x for x in pairs if x[1].get("x_floor")), key=lambda x: -x[1]["x_floor"]
    )[:TOP_USED]
    blocks = [
        "<h2>Most used</h2>"
        '<p class="muted small">Ranked by how far above its platform\'s noise '
        "floor a package is, which compares across platforms.</p>"
        + _mini(
            used,
            lambda r: (
                f"{num(r['downloads']['30d'])} <span "
                f'class="muted small">{times(r["x_floor"])}</span>'
            ),
        )
        + _see_all(summary, daily)
    ]

    steady = [x for x in pairs if is_steady(x[1], x[0])]
    up = sorted((x for x in steady if gain(x[1]) > 0), key=lambda x: -gain(x[1]))
    down = sorted((x for x in steady if gain(x[1]) < 0), key=lambda x: gain(x[1]))

    def move(r):
        return f"{signed(gain(r)).strip()}"

    blocks.append(
        '<h2>Movers</h2><p class="muted small">Largest change in 30-day downloads, '
        "among packages above the noise in both windows.</p>"
        '<div class="two"><div><h3>Up</h3>'
        + _mini(up[:TOP_MOVERS], move)
        + "</div><div><h3>Down</h3>"
        + _mini(down[:TOP_MOVERS], move)
        + "</div></div>"
        + f'<p class="small">{tab_link("movers", "See all movers")} →</p>'
    )

    dep_m = DEPENDENT_METRICS[0]
    depended = sorted(
        (x for x in pairs if metric(x[1], dep_m)),
        key=lambda x: -(metric(x[1], dep_m) or 0),
    )
    if depended:
        blocks.append(
            f'<h2>Depended on</h2><p class="muted small">Packages other packages '
            f"declare as a dependency ({len(depended)}), the sign of use a robot "
            "does not create.</p>"
            + _mini(
                depended[:TOP_DEPENDED],
                lambda r: (
                    f'{num(metric(r, dep_m))} <span class="muted small">'
                    f"{label(dep_m).removeprefix('dependent ')}</span>"
                ),
            )
            + _see_all(
                summary,
                [
                    p
                    for p in daily
                    if any(metric(r, dep_m) for m, r in pairs if m is ps[p])
                ],
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
            f'<tr>{name_cell(r)}<td class="num">{num(metric(r, m))} '
            f'<span class="muted small">{label(m)}</span></td></tr>'
            for r in top
        )
        blocks.append(
            f"<h2>Top {e(meta['title'])} {unit_of(meta)} by {label(m)}</h2>"
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
    daily = [
        p
        for p in daily_platforms(summary)
        if any(p in g["rows"] for g in groups.values())
    ]
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
        xf = max(
            (r.get("x_floor") or 0 for p in daily for r in g["rows"].get(p, [])),
            default=0,
        )
        stars = sum(
            tot(g, p, lambda r, m=ps[p]["headline"][0]: metric(r, m) or 0)
            for p in snaps
            if ps[p]["headline"]
        )
        return (-xf, -stars, item[0])

    full_rows.sort(key=score)
    head = th("name", "project", cls="name")
    # on a phone: the first platform's downloads, dependents, the first headline
    head += "".join(
        th(f"dl-{p}", f"{e(ps[p]['title'])} 30d", cls="num" + (" c-x" if i else ""))
        for i, p in enumerate(daily)
    )
    head += th("deps", "dependents", cls="num")
    for p in snaps:
        head += "".join(
            th(f"{p}-{m}", label(m), cls="num" + ("" if i == 0 else " c-x"))
            for i, m in enumerate(ps[p]["headline"])
        )
    body = []
    for i, (key, g) in enumerate(full_rows):
        name = (
            key.split("/", 3)[-1]
            if key.startswith("https://")
            else key.split(":", 1)[1]
        )
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
        cells.append(
            f'<td class="num" data-v="{deps}">{num(deps) if deps else ""}</td>'
        )
        for p in snaps:
            for j, m in enumerate(ps[p]["headline"]):
                v = (
                    tot(g, p, lambda r, m=m: metric(r, m) or 0)
                    if p in g["rows"]
                    else None
                )
                cells.append(
                    f'<td class="num{"" if j == 0 else " c-x"}" '
                    f'data-v="{"" if v is None else v}">{"" if v is None else num(v)}</td>'
                )
        q = e(
            f"{name} {' '.join(str(r['package']) for rs in g['rows'].values() for r in rs)}".lower()
        )
        body.append(f'<tr class="r" data-i="{i}" data-q="{q}">{"".join(cells)}</tr>')

    note = ""
    if empty:
        links = ", ".join(
            link(
                g["repo"] or "", k.split("/", 3)[-1] if k.startswith("https://") else k
            )
            for k, g in sorted(empty)
        )
        what = " and no ".join(
            label(ps[p]["headline"][0]) for p in snaps if ps[p]["headline"]
        )
        unit_word = (
            "/".join(sorted({ps[p].get("unit") or "packages" for p in snaps}))
            or "projects"
        )
        n_snap = sum(len(rows_of(summary, p)) for p in snaps)
        note = (
            f'<details class="small"><summary>{units(len(empty), e(unit_word))}'
            f" with no package and no {what} (of {n_snap:,})</summary>"
            f"<p>{links}</p></details>"
        )
    return f"""
<section class="tbl" data-view="projects" data-sort="" data-limit="{DFLT_ROW_LIMIT}">
<h2>Projects <span class="muted small">{plural(len(full_rows), "project")}</span></h2>
<p class="muted small">Packages joined to the repository they declare: what one
project reaches across platforms.</p>
<div class="controls jsonly"><input type="search" class="q" placeholder="Search project or package"
 aria-label="Search projects" autocomplete="off"></div>
{table_html(head, body)}
<p class="rowsnote jsonly"><button type="button" class="btn more" hidden></button>
<span class="muted small count" role="status"></span></p>
{note}
</section>"""


# --------------------------------------------------------------------------- #
# Movers


def _mover_table(rows: list[Row]) -> str:
    if not rows:
        return '<p class="muted small">None.</p>'
    body = "".join(
        f"<tr>{name_cell(r)}"
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
    for p in daily_platforms(summary):
        meta = ps[p]
        steady = [r for r in rows_of(summary, p) if is_steady(r, meta)]
        up = sorted((r for r in steady if gain(r) > 0), key=lambda r: -gain(r))
        down = sorted((r for r in steady if gain(r) < 0), key=gain)
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
