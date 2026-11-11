"""The operations, as plain functions: JSON-able arguments in, JSON-able dicts out.

This is the single source of truth for every surface: the CLI dispatches
:data:`COMMANDS` with ``cw`` (:mod:`pkgreach.__main__`), and an MCP or HTTP
adapter would reference ``pkgreach.tools:collect`` and so on. Each function
does the wiring a caller should not have to: reading the settings file,
opening the folders, giving the transport the GitHub token from the
environment.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from pkgreach.collect import collect as _collect
from pkgreach.config import DFLT_CONFIG_FILENAME, DFLT_DATA_DIR, load_settings
from pkgreach.http import make_http
from pkgreach.platforms import PLATFORMS
from pkgreach.platforms.github import auth_headers, token_from_env
from pkgreach.render import DFLT_TITLE, DFLT_VIEW
from pkgreach.report import build_site
from pkgreach.scaffold import DFLT_CRON, default_action_ref, init_repo
from pkgreach.tables import Files


class CollectionFailed(RuntimeError):
    """Raised by :func:`collect` with ``fail_on_errors`` when something failed."""


def collect(
    *,
    config: str = DFLT_CONFIG_FILENAME,
    data_dir: str = str(DFLT_DATA_DIR),
    fail_on_errors: bool = False,
    environ: Mapping[str, str] = os.environ,
) -> dict:
    """Fetch this week's numbers for the packages in ``config`` into ``data_dir``.

    The GitHub token, if any, comes from ``GITHUB_TOKEN`` or ``GH_TOKEN``.
    """
    settings = load_settings(config, known_platforms=PLATFORMS)
    http = make_http(headers_by_host=auth_headers(token_from_env(environ)))
    report = _collect(settings, store=Files(Path(data_dir)), http=http, log=print)
    if fail_on_errors and report.errors:
        raise CollectionFailed(f"{len(report.errors)} errors; see last_run.json")
    return {
        "packages": report.packages,
        "errors": len(report.errors),
        "files_changed": report.files_changed,
        "duration_s": report.duration_s,
    }


def report(
    *,
    data_dir: str = str(DFLT_DATA_DIR),
    out: str = "site",
    title: str = DFLT_TITLE,
    default_view: str = DFLT_VIEW,
) -> dict:
    """Write the report site (``index.html``, ``summary.json``) into ``out``.

    ``default_view``: the view the page opens on: ``overview``, a platform
    (``pypi``, ``npm``, ...), ``all``, ``projects`` or ``movers``.
    """
    s = build_site(
        Files(Path(data_dir)),
        Files(Path(out)),
        title=title,
        default_view=default_view,
    )
    return {"out": out, "packages": len(s["packages"]), "as_of": s["as_of"]}


def init(
    directory: str,
    *,
    pypi: Sequence[str] = (),
    npm: Sequence[str] = (),
    crates: Sequence[str] = (),
    github: Sequence[str] = (),
    cron: str = DFLT_CRON,
    action_ref: str = "",
    overwrite: bool = False,
) -> dict:
    """Write ``pkgreach.toml`` and a weekly workflow into the repo at ``directory``.

    Name your accounts per platform (``--pypi you --github you your-org``).
    """
    users = {"pypi": pypi, "npm": npm, "crates": crates, "github": github}
    written = init_repo(
        directory,
        users={k: list(v) for k, v in users.items() if v},
        cron=cron,
        action_ref=action_ref or default_action_ref(),
        overwrite=overwrite,
    )
    return {"written": written}


COMMANDS = [collect, report, init]
