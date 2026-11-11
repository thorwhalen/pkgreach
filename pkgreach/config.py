"""Settings: which packages, on which platforms.

A ``pkgreach.toml`` has one table per platform, each a :class:`Selection`::

    [pypi]
    users = ["alice"]                 # every package these accounts maintain
    packages = ["some-other-package"] # plus these
    exclude = ["alice-test-*"]        # minus these (glob patterns)

    [github]
    users = ["alice", "alice-org"]    # repos of these owners (public only)
    where = { fork = false, archived = false }   # characteristics to keep

Every key is optional and unknown keys are refused, so a typo never silently
falls back to a default. In Python, ``collect(select=...)`` adds a predicate
over each package's metadata, for selections a TOML file cannot express.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

DFLT_CONFIG_FILENAME = "pkgreach.toml"
DFLT_DATA_DIR = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    / "pkgreach"
    / "data"
)
#: Top-level keys that are run options, not platforms.
RUN_KEYS = ("max_workers", "dependents")


class SettingsError(ValueError):
    """A settings file that is missing or wrong (a user error, not a bug)."""


@dataclass(frozen=True)
class Selection:
    """Which packages of one platform to follow.

    Attributes:
        users: accounts (users, maintainers, orgs) whose packages are all followed.
        packages: packages followed by name, in addition to the users' ones.
        exclude: glob patterns of package names to drop (``"*-test"``).
        where: metadata a package must match to be kept, field by field
            (``{"fork": False}``). Fields a platform does not report never match.
    """

    users: tuple[str, ...] = ()
    packages: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    where: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    """What to collect: a :class:`Selection` per platform, and run options.

    Attributes:
        platforms: platform name to selection; a platform absent here is skipped.
        max_workers: concurrent requests per platform.
        dependents: also record dependent packages and repositories
            (from ecosyste.ms), the strongest sign of real use.
    """

    platforms: Mapping[str, Selection] = field(default_factory=dict)
    max_workers: int = 4
    dependents: bool = True


def _tuple(v) -> tuple[str, ...]:
    return (v,) if isinstance(v, str) else tuple(v)


def _selection(platform: str, d: Mapping) -> Selection:
    known = [f.name for f in fields(Selection)]
    unknown = sorted(set(d) - set(known))
    if unknown:
        raise SettingsError(
            f"Unknown key(s) {unknown} in [{platform}]; valid keys are {known}."
        )
    kw = {k: _tuple(d[k]) for k in ("users", "packages", "exclude") if k in d}
    return Selection(**kw, where=dict(d.get("where", {})))


def settings_from_mapping(d: Mapping, *, known_platforms=None) -> Settings:
    """Settings from a parsed TOML document (or any nested mapping)."""
    d = dict(d.get("pkgreach", d))
    run = {k: d.pop(k) for k in RUN_KEYS if k in d}
    if known_platforms is not None:
        unknown = sorted(set(d) - set(known_platforms))
        if unknown:
            raise SettingsError(
                f"Unknown platform(s) or setting(s) {unknown}; platforms are "
                f"{sorted(known_platforms)}, settings are {list(RUN_KEYS)}."
            )
    return Settings(
        platforms={name: _selection(name, sel) for name, sel in d.items()}, **run
    )


def load_settings(path: str | os.PathLike, *, known_platforms=None) -> Settings:
    """Settings from a TOML file; a missing or invalid file raises :class:`SettingsError`."""
    p = Path(path)
    if not p.exists():
        raise SettingsError(
            f"No settings file at {p}. Write one (`pkgreach init`) that lists "
            'your accounts per platform, e.g. [pypi] users = ["you"].'
        )
    try:
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise SettingsError(f"{p} is not valid TOML: {e}") from None
    return settings_from_mapping(doc, known_platforms=known_platforms)
