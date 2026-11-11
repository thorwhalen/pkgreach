# pkgreach

How are your packages really used? `pkgreach` tracks your packages on PyPI, npm, crates.io and GitHub every week, keeps the history the registries throw away, and publishes a report that separates robots from people.

**Live example (the author's packages):** https://thorwhalen.github.io/pkgreach/

## Why

Registries keep a few months of daily download counts (crates.io 90 days, PyPI about 6 months, npm 18 months), and none of them separates people from robots: mirrors, CI pipelines and scanners download every release of every package. So `pkgreach` reports downloads against a **noise floor** (what your least-used packages get), next to the signals a robot does not create: **dependents** (packages and repositories that declare yours, from [ecosyste.ms](https://ecosyste.ms)), and **stars and forks** of your public repositories.

## Quick start: a weekly GitHub Action

In any repository you own (it can be public: everything collected is public already):

```bash
pip install pkgreach
pkgreach init . --pypi YOUR_PYPI_USER --npm YOUR_NPM_USER --github YOUR_GITHUB_USER
git add -A && git commit -m "pkgreach" && git push
```

`pkgreach init` writes `pkgreach.toml` (what to follow) and `.github/workflows/pkgreach.yml`. Then turn on Pages once (Settings → Pages → Source: **GitHub Actions**) and run the workflow (`gh workflow run pkgreach.yml`). Every Sunday after that it collects, commits the history to the `pkgreach-data` branch, and publishes the report on your GitHub Pages. No secret is needed.

The workflow is three steps:

```yaml
- uses: actions/checkout@v4
- uses: thorwhalen/pkgreach@<version>   # pin the release you installed
  id: reach
- uses: actions/upload-pages-artifact@v3
  with:
    path: ${{ steps.reach.outputs.site-dir }}
- uses: actions/deploy-pages@v4
```

## Configuration

`pkgreach.toml` has one table per platform: `pypi`, `npm`, `crates`, `github`. Every key is optional; unknown keys are refused, so a typo never silently does nothing.

```toml
[pypi]
users = ["alice"]                    # every package these accounts own or maintain
packages = ["a-package-of-a-friend"] # plus these
exclude = ["alice-test-*"]           # minus these (glob patterns)

[npm]
users = ["alice"]

[crates]
users = ["alice"]                    # crates.io login

[github]
users = ["alice", "alice-org"]       # public repos of these users and orgs
where = { fork = false, archived = false }   # characteristics a package must have
```

`where` matches metadata field by field (GitHub repos have `fork`, `archived`, `language`; PyPI packages have `role`, `owner` or `maintainer`). Top-level keys: `max_workers` (default 4) and `dependents` (default `true`: ask ecosyste.ms).

## Run it locally

```bash
pkgreach collect --config pkgreach.toml   # into ~/.local/share/pkgreach/data
pkgreach report --out site                # site/index.html and site/summary.json
```

From Python, every part is a keyword argument with a working default:

```python
from pkgreach import collect, load_settings, build_site, Files, PLATFORMS

collect(load_settings("pkgreach.toml"), store=Files("data"))
build_site(Files("data"), Files("site"))
```

- `collect(platforms=...)`: add a platform with `Platform(name, list_packages, fetch)`; see `pkgreach/platforms/__init__.py` for the two functions' contract.
- `collect(select=lambda platform, record: ...)`: any selection a TOML file cannot express.
- `collect(dependents=...)`: another source of dependents.
- `build_site(analyze=..., render=...)`: your own summary or page; `summary.json` is the default summary, for any other tool.
- `store=` / `out=`: any `MutableMapping[str, str]`, such as a [dol](https://github.com/i2mint/dol) store (S3, a database).

## What is collected

| platform | daily downloads | other numbers | source |
|---|---|---|---|
| PyPI | all, and without mirrors | versions, dependents | pypistats.org, PyPI JSON, ecosyste.ms |
| npm | all | dependents | api.npmjs.org, ecosyste.ms |
| crates.io | all | total downloads, versions, dependents | crates.io, ecosyste.ms |
| GitHub | none | stars, forks, open issues and PRs | GitHub REST (public repos only) |

The history is plain CSV, one table per kind, split by year (`downloads/YYYY.csv`, `metrics.csv`, `packages.csv`, `runs.csv`), merged idempotently so re-running a collection never changes the result. `manifest.json` lists every file and its columns. Design and alternatives: [docs/adr/0001-seams-and-scope.md](docs/adr/0001-seams-and-scope.md). What each platform offers, verified: [docs/research/platform-apis.md](docs/research/platform-apis.md).

**GitHub traffic** (views, clones, referrers) is private and needs a token with push access. That is [ghtraffic](https://github.com/thorwhalen/ghtraffic)'s job, in a private repository; pkgreach reuses its storage layer.

## Limits

- History starts at your first run, minus what the registry still keeps.
- One run of about 400 packages takes about 7 minutes, mostly waiting on pypistats.org's limit of 60 requests a minute.
- Listing a PyPI account uses PyPI's XML-RPC `user_packages`, deprecated but still answered.
- Dependents come from ecosyste.ms, which indexes new packages with some delay: a fresh package shows none at first.
