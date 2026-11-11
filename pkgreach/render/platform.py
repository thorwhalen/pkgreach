"""A platform's tab: search, sort, a noise toggle, and its table.

Tables are rendered complete and in their default order (signal first, noise
last), so the page reads without JavaScript; the script only filters, sorts
and shortens them (see :mod:`pkgreach.render.assets`).
"""

from __future__ import annotations

from collections.abc import Mapping

from pkgreach.render.fmt import (
    e,
    full,
    label,
    metric,
    num,
    pct,
    signed,
    spark,
    times,
    unit_of,
    units,
)
from pkgreach.render.read import (
    DEPENDENT_METRICS,
    DFLT_ROW_LIMIT,
    Row,
    is_quiet,
    name_cell,
    signal_x,
    table_html,
    th,
)

# --------------------------------------------------------------------------- #
# Change, as a cell


def change_cell(r: Row) -> str:
    """Growth relative to the platform's median, or why there is none."""
    if not r.get("has_downloads"):
        return '<td class="num" data-v="">–</td>'
    if not r.get("prev_covered", True):
        return '<td class="num" data-v=""><span class="tag">new</span></td>'
    if r.get("prev_low_base"):
        return '<td class="num" data-v=""><span class="tag">low base</span></td>'
    g = r.get("growth_vs_median_30d")
    return f'<td class="num" data-v="{"" if g is None else g}">{pct(g)}</td>'


def _chg_label(meta: Mapping) -> str:
    return "vs median"


# --------------------------------------------------------------------------- #
# Platform tables


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
        th("name", "package", cls="name")
        + th("30d", "30 days", cls="num")
        + th("chg", _chg_label(meta), cls="num")
        + th("x", "× floor", cls="num c-x")
        + "".join(
            th(m, label(m).replace("dependent ", "dependent<br>"), cls="num c-dep")
            for m in deps
        )
        + '<th class="c-spark">26 weeks</th>'
    )
    body = []
    for i, r in enumerate(rows):
        xf = r.get("x_floor")
        quiet = " quiet" if is_quiet(r, meta) else ""
        cells = [
            name_cell(r, _chip(r, deps)),
            f'<td class="num" data-v="{r["downloads"]["30d"]}">'
            f"{num(r['downloads']['30d'])}</td>",
            change_cell(r),
            f'<td class="num c-x" data-v="{"" if xf is None else xf}">{times(xf)}</td>',
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
    return table_html(head, body), sorts


def snapshot_table(rows: list[Row], meta: Mapping) -> tuple[str, list[tuple[str, str]]]:
    """The table of a snapshot platform: its headline metrics, with 30-day changes."""
    head_ms = meta["headline"]
    first = head_ms[0] if head_ms else None
    rows = sorted(
        rows,
        key=lambda r: (is_quiet(r, meta), -(metric(r, first) or 0), r["package"]),
    )
    head = th("name", "name", cls="name") + "".join(
        th(m, label(m), cls="num") for m in head_ms
    )
    body = []
    for i, r in enumerate(rows):
        cells = [name_cell(r)]
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
    return table_html(head, body), sorts


def _noise_tip(name: str, meta: Mapping) -> str:
    if meta["kind"] == "snapshot":
        return (
            f"{unit_of(meta).capitalize()} with no "
            f"{' and no '.join(label(m) for m in meta['headline'])} are dimmed "
            "and listed last."
        )
    floor, sx = meta.get("noise_floor_30d"), signal_x(meta)
    med = meta.get("median_growth_30d")
    return (
        f"The noise floor is {full(floor)} downloads in 30 days: what the least-used "
        f"{unit_of(meta)} here get from mirrors, CI and bots. Rows under {sx:g}× "
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
<h2>{title} <span class="muted small">{units(len(rows), unit_of(meta))}</span>
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
