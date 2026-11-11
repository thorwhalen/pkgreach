"""Rendering: from a summary to the report page.

:func:`render_page` is the default of the ``render=`` seam of
:func:`pkgreach.report.build_site`: one self-contained ``index.html`` with
client-side views (Overview, one tab per platform, All, Projects, Movers).
Any callable ``render(summary, *, title, default_view)`` returning the page's
HTML (or a mapping of file names to contents) can replace it.

- :mod:`~pkgreach.render.page`: the page, the view names, ``default_view``.
- :mod:`~pkgreach.render.views`: one function per view.
- :mod:`~pkgreach.render.assets`: the inline CSS and script.
- :mod:`~pkgreach.render.fmt`: escaping and number formatting.
"""

from pkgreach.render.page import (
    DFLT_TITLE,
    DFLT_VIEW,
    FIXED_VIEWS,
    render_page,
    views_of,
)

__all__ = ["DFLT_TITLE", "DFLT_VIEW", "FIXED_VIEWS", "render_page", "views_of"]
