"""Command line: ``pkgreach collect | report | init``.

``pkgreach collect --config pkgreach.toml --data-dir data`` merges this
week's numbers into the history; ``pkgreach report --data-dir data --out
site`` writes the static report. Without ``--data-dir``, data goes to
``~/.local/share/pkgreach/data``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ghtraffic.tables import Files

from pkgreach.collect import collect
from pkgreach.config import DFLT_CONFIG_FILENAME, DFLT_DATA_DIR, load_settings
from pkgreach.platforms import PLATFORMS
from pkgreach.report import DFLT_TITLE, build_site
from pkgreach.scaffold import DFLT_CRON, default_action_ref, init_repo


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pkgreach", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="fetch this week's numbers into the history")
    c.add_argument("--data-dir", default=str(DFLT_DATA_DIR))
    c.add_argument("--config", help=f"default: ./{DFLT_CONFIG_FILENAME}")
    c.add_argument(
        "--fail-on-errors", action="store_true", help="exit 1 if any package failed"
    )

    r = sub.add_parser("report", help="write the static report site")
    r.add_argument("--data-dir", default=str(DFLT_DATA_DIR))
    r.add_argument("--out", required=True, help="folder to write the site into")
    r.add_argument("--title", default=DFLT_TITLE)

    i = sub.add_parser("init", help="write a config and a weekly workflow into a repo")
    i.add_argument("dir", nargs="?", default=".")
    for name in PLATFORMS:
        i.add_argument(f"--{name}", action="append", default=[], metavar="USER")
    i.add_argument("--cron", default=DFLT_CRON)
    i.add_argument("--action-ref", help="default: this pkgreach's release tag")
    i.add_argument("--overwrite", action="store_true")
    return p


def main(argv=None) -> int:
    """Entry point of the ``pkgreach`` command."""
    args = _parser().parse_args(argv)
    if args.cmd == "collect":
        settings = load_settings(
            args.config or DFLT_CONFIG_FILENAME, known_platforms=PLATFORMS
        )
        report = collect(settings, store=Files(Path(args.data_dir)), log=print)
        return 1 if (args.fail_on_errors and report.errors) else 0
    if args.cmd == "report":
        s = build_site(Files(args.data_dir), Files(args.out), title=args.title)
        print(f"pkgreach: report of {len(s['packages'])} packages in {args.out}")
        return 0
    if args.cmd == "init":
        users = {name: getattr(args, name) for name in PLATFORMS}
        written = init_repo(
            args.dir,
            users={k: v for k, v in users.items() if v},
            cron=args.cron,
            action_ref=args.action_ref or default_action_ref(),
            overwrite=args.overwrite,
        )
        print("\n".join(written) or "nothing written (files exist; --overwrite)")
        return 0
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
