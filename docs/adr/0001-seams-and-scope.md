# ADR 0001: one public package, five seams, public numbers only

- Status: accepted
- Date: 2026-11-11

## Context

The request: a public tool that anyone can set up as a scheduled CI job to track engagement and usage of their packages on GitHub, PyPI, npm and crates.io (and other platforms worth supporting), and update an analytics report. Publishing platform, package selection (list, pattern, characteristics), stats and analysis, and the analysis target must all be seams. The author's own instance runs every Sunday from the public repository, with nothing private in public files.

What the platforms offer, verified live on 2026-11-11, is in [docs/research/platform-apis.md](../research/platform-apis.md). The facts that shape the design:

- Every download count and dependents count we need is public and keyless: pypistats.org, api.npmjs.org, crates.io (with a User-Agent), ecosyste.ms, and the GitHub REST API for public repos.
- Daily counts expire: pypistats keeps about 180 days, crates.io 90, npm 18 months. A history must be accumulated, weekly is often enough, and an idempotent merge makes overlaps harmless.
- Raw downloads are mostly robots (mirrors, CI, scanners: npm gives each release 100 to 150 bot downloads [research §8]). Dependents and stars are the signals a robot does not create.
- GitHub *traffic* (views, clones, referrers) is private, needs push access, and is already collected by ghtraffic into a private repository.

## Decision

**A new package, `pkgreach`, depending on `ghtraffic`; not a rename of ghtraffic.** ghtraffic's name, PyPI project, Action tag, Pages dashboard and private data repository are all GitHub-traffic specific and in use. pkgreach reuses its table store (`ghtraffic.tables`: year-partitioned long-form CSV, idempotent merges, a `MutableMapping` store), which gained a generic `entity=` for change-only tables to serve this second consumer (thorwhalen/ghtraffic#6). Name checked free on PyPI, npm, crates.io and GitHub on 2026-11-11.

**Fleet search** (2026-11-11): `yp` lists a PyPI account by scraping `pypi.org/user/`, now behind a JavaScript challenge, and needs bs4: not used, the XML-RPC listing here is its replacement (issue filed on yp). `cw` is used for the CLI. `dol`'s `Files` duplicates ghtraffic's: kept ghtraffic's for a zero-dependency Action install, and the store's extraction is filed on ghtraffic. No fleet package reads download counts or dependents.

**Public numbers only.** pkgreach collects what is already public: downloads, dependents, versions, and the stars, forks and open issues of *public* repositories (private ones are dropped even if the token sees them). So its history and report can live in a public repository and on GitHub Pages, and the workflow needs no secret: the workflow's own `GITHUB_TOKEN` reads GitHub and pushes the history. Private GitHub traffic stays with ghtraffic in a private repository.

**The seams**, each one keyword argument with a working default:

| # | Seam | v1 default | Replacement we can point at |
|---|---|---|---|
| 1 | platform: `collect(platforms=)` and `summarize(platforms=)`, a mapping of `Platform` (how to list and fetch, plus how to present: `title`, `kind` daily or snapshot, `headline` metrics, `preferred_series`, `ecosystem`, `normalize`, `prune_unlisted`) | PyPI, npm, crates.io, GitHub | Hugging Face, conda-forge, Docker Hub, Open VSX, JSR (research §6): snapshot platforms need no change to the analysis or the page |
| 2 | selection: per-platform `Selection(users, packages, exclude, where)` in `pkgreach.toml`, plus `collect(select=)` | listed packages matching `where`, plus named ones, minus globs | the request ("list? pattern? characteristics?") |
| 3 | dependents: `collect(dependents=)`, keyed by ecosystem (purl type) | ecosyste.ms | deps.dev, crates.io reverse dependencies |
| 4 | analysis: `build_site(analyze=)` | `summarize` (per-platform windows ending at its last complete day, growth, noise floor) | ClickHouse PyPI breakdowns by installer/OS (research §1) |
| 5 | target: `store=` / `out=` (`MutableMapping[str, str]`), and the Action's `data-branch` / `site-dir` | a folder; history on the `pkgreach-data` branch; site on GitHub Pages | any dol store, any static host |

The transport (`http=`) is also injectable, for tests and caches; credentials reach it as `make_http(headers_by_host=)`, never from inside a platform.

`NOT seams:` the CSV layout (ghtraffic's), the report's HTML and CSS (a `render=` seam waits for a second renderer), CLI parsing, the noise-floor quantile (a keyword argument of `summarize`, not a pluggable strategy).

**Surfaces:** `pkgreach/tools.py` holds the operations as plain functions, JSON-able in and out (`collect`, `report`, `init`), and is the single source for every surface. Built: the CLI (`cw.dispatch` over `tools.COMMANDS`) and a composite GitHub Action. Not built: MCP (it would reference `pkgreach.tools:collect` etc. with no core change), HTTP, an agent skill. The author's own workflow is generated from the same template as `pkgreach init`'s (a test keeps them identical).

**Tables** (`pkgreach.tables.TABLES`): `downloads/YYYY.csv` (`date, platform, package, series, count`, max merge, zero days absent); `metrics.csv` (`date, platform, package, metric, value`, one row per change); `packages.csv` (metadata, with `history_from`, the first day covered, so a missing day reads as zero after it and unknown before it); `runs.csv`. PyPI keeps two series, `all` and `without_mirrors`; the analysis prefers the latter.

**Noise floor.** Per platform, the 25th percentile of 30-day downloads among followed packages that were downloaded at all. It is an estimate, labelled as one on the page; `× floor` is a package's 30-day count over it.

**Privacy of a public history:** only public repositories are listed, and a repo that leaves the listing (made private, deleted, or dropped from the selection) is removed from the current `packages` and `metrics` tables at the next run (`prune_unlisted`), and from the page at once. What was committed before stays in the branch's git history.

**Attribution:** dependents are ecosyste.ms data, CC BY-SA 4.0. The page credits it, `summary.json` carries an `attribution` key, and the history holds a `DATA-LICENSE.md`.

**Cadence:** weekly, Sundays 05:23 UTC. The shortest window kept (crates.io, 90 days) survives a dozen missed runs; re-fetching overlaps by 7 days so revised recent days are picked up.

## Consequences

- One run of the author's selection (about 280 PyPI packages, 70 npm, 340 public repos) takes about 7 minutes, almost all of it waiting on pypistats.org's 60-requests-a-minute limit and npm's burst limit. Public-repository Actions minutes are free.
- PyPI listing relies on the XML-RPC `user_packages` call, deprecated but answered. If it goes, ecosyste.ms `/maintainers/{user}/packages` is the fallback, at the `list_packages` boundary.
- pypistats' `recent` totals disagree with its own daily series; we only use the daily series.
- Before a package's first collection, history is limited to what the registry still has (npm 18 months, PyPI about 6, crates.io 3). ClickHouse's public PyPI dataset could backfill PyPI from 2020: a candidate for the analysis or platform seam, not v1.
- The table store's home is ghtraffic for now; all imports of it go through `pkgreach/tables.py`, so extracting it into its own package (filed on ghtraffic) changes one file.
- The private traffic view and this public view are two pages for now. Joining them (the ghtraffic dashboard reading this history, or this report linking a private section) is a follow-up.
