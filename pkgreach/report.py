"""The report: a static site (``index.html``, ``summary.json``, ``last_run.json``).

:func:`build_site` reads the history, summarizes it (the ``analyze=`` seam),
renders the summary (the ``render=`` seam) and writes the site into ``out``,
any ``MutableMapping[str, str]``: a folder by default, which any static host
serves (GitHub Pages, your own server, an S3 bucket through a ``dol`` store).

The default rendering is :func:`pkgreach.render.render_page`: one page with
client-side views, the data baked in, nothing fetched at view time.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any

from pkgreach.analyze import summarize
from pkgreach.render import DFLT_TITLE, DFLT_VIEW, render_page
from pkgreach.tables import LAST_RUN_KEY, SUMMARY_KEY

Summary = dict[str, Any]
#: ``render(summary, *, title, default_view)``: the page's HTML, or a mapping
#: of file names to contents (``index.html`` among them) for several pages.
Render = Callable[..., "str | Mapping[str, str]"]

#: The default page, under the name earlier versions exported.
render_html = render_page


def build_site(
    store: MutableMapping,
    out: MutableMapping,
    *,
    analyze: Callable[[MutableMapping], Summary] = summarize,
    render: Render = render_page,
    default_view: str = DFLT_VIEW,
    title: str = DFLT_TITLE,
) -> Summary:
    """Summarize the history in ``store`` and write the site into ``out``.

    ``analyze`` is the seam for another summary (it must return the shape of
    :func:`~pkgreach.analyze.summarize`, which ``summary.json`` documents);
    ``render`` the seam for another page from the same summary.
    ``default_view`` is the view a bare URL opens (see
    :func:`~pkgreach.render.render_page`). The last run's log
    (``last_run.json``) is published next to the page when the store has one.
    """
    summary = analyze(store)
    page = render(summary, title=title, default_view=default_view)
    out[SUMMARY_KEY] = json.dumps(summary, indent=1) + "\n"
    if LAST_RUN_KEY in store:
        out[LAST_RUN_KEY] = store[LAST_RUN_KEY]
    for key, content in ({"index.html": page} if isinstance(page, str) else page).items():
        out[key] = content
    return summary
