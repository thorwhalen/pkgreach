# PYTHON_ARGCOMPLETE_OK
"""Command line: ``pkgreach collect | report | init``, one command per function
of :data:`pkgreach.tools.COMMANDS` (dispatched by ``cw``).

``pkgreach collect --config pkgreach.toml --data-dir data`` merges this week's
numbers into the history; ``pkgreach report --data-dir data --out site``
writes the static report; ``pkgreach init . --pypi you --github you`` sets up
a repository. Without ``--data-dir``, data goes to ``~/.local/share/pkgreach/data``.
"""

from __future__ import annotations

import sys

import cw

from pkgreach.config import SettingsError
from pkgreach.tools import COMMANDS, CollectionFailed

#: Keep injection-only parameters off the command line.
_CLI_CONFIG = {"collect": {"environ": cw.HIDE}}


def main(argv=None) -> int:
    """Entry point of the ``pkgreach`` command; returns the exit code."""
    try:
        return cw.dispatch(
            COMMANDS, argv=argv, config=_CLI_CONFIG, convention=cw.MODERN
        )
    except (CollectionFailed, SettingsError) as e:
        print(f"pkgreach: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
