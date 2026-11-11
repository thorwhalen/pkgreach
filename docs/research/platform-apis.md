# Package usage and engagement statistics: platform research

Date: 2026-11-11. Scope: what a stdlib-only Python tool, run weekly from GitHub Actions with no paid services, can collect about one person's published packages on PyPI, npm, crates.io, GitHub and other registries. Every claim marked "verified live" was checked with a curl call on 2026-11-11 against public packages (`requests`, `left-pad`, `serde`, `dol`) or the accounts `thorwhalen1` (PyPI, npm) and `thorwhalen` (crates.io, Hugging Face). Claims taken only from documentation say so; claims not checked are marked "unverified".

## Summary table

| Platform | Count endpoint (no key unless stated) | Auth | History window | User-package listing | Dependents source |
|---|---|---|---|---|---|
| PyPI (pypistats.org) | `pypistats.org/api/packages/{p}/{recent,overall,system,python_major,python_minor}` | none | daily; documented 180 days, observed 217 days (2026-04-08 to 2026-11-10) | XML-RPC `user_packages` (deprecated, works: 284 rows for thorwhalen1); user page HTML is behind a JS challenge | deps.dev, ecosyste.ms, libraries.io |
| PyPI (ClickHouse / ClickPy) | `POST https://sql-clickhouse.clickhouse.com/?user=demo` with SQL on `pypi.*` | none (public read-only `demo` user) | daily from 2020-09-28 to yesterday; by version, installer, Python, system, country | `pypi.projects` has author/maintainer strings, not PyPI accounts | none |
| PyPI (BigQuery) | `bigquery-public-data.pypi.file_downloads` | Google account + service-account key (free sandbox) | full raw log history; 1 TiB scanned per month free | no | none |
| PyPI (pepy.tech) | `api.pepy.tech/api/v2/projects/{p}`; badges at `static.pepy.tech/badge/{p}` | free key for JSON (5 rpm); badges need none | 3 months daily on free tier; all-time total | no | none |
| npm | `api.npmjs.org/downloads/{point,range}/{period}/{pkg}`; `/versions/{pkg}/last-week` | none | daily from 2015-01-10; max 18 months per query (365 days for bulk); per-version only last 7 days | `registry.npmjs.org/-/v1/search?text=maintainer:{u}` (70) or `registry.npmjs.org/-/user/{u}/package` (70) | npm search result `dependents` field; deps.dev; ecosyste.ms |
| crates.io | `crates.io/api/v1/crates/{c}` (total, `recent_downloads`); `/crates/{c}/downloads` | none, but a descriptive User-Agent is mandatory (403 without) | 90 days daily per version via API; older days in `static.crates.io/archive/version-downloads/{date}.csv` | `/api/v1/users/{login}` gives id, then `/api/v1/crates?user_id={id}` | `/api/v1/crates/{c}/reverse_dependencies` (meta.total) |
| GitHub | traffic `/repos/{o}/{r}/traffic/*`; stars `/repos/{o}/{r}/stargazers/history` | traffic: push token; star history: none | traffic 14 days; star history full life, weekly buckets with daily counts | `/users/{u}/repos` | HTML scrape of `/{o}/{r}/network/dependents` only |
| deps.dev | `api.deps.dev/v3alpha/systems/{sys}/packages/{p}/versions/{v}:dependents` | none | current snapshot | no | yes: direct/indirect, per version; npm, PyPI, Cargo, Maven, Go, NuGet, RubyGems |
| ecosyste.ms | `packages.ecosyste.ms/api/v1/registries/{reg}/packages/{p}` | none (5000 req/h anonymous observed) | snapshot: last-month or total downloads | `/registries/{reg}/maintainers/{u}/packages` | yes: `dependent_packages_count`, `dependent_repos_count` |
| libraries.io | `libraries.io/api/{platform}/{p}` | free key documented (60/min); anonymous works at 10/hour | snapshot | `/api/{platform}/...` per user is keyed (unverified) | `dependents_count`, `dependent_repos_count` |
| conda / anaconda.org | `api.anaconda.org/package/{channel}/{p}` (`ndownloads`) | none | all-time per file; monthly/hourly parquet on public S3 | `/packages/{owner}` (slow for big channels) | ecosyste.ms `conda-forge.org` |
| Docker Hub | `hub.docker.com/v2/repositories/{ns}/{repo}/` (`pull_count`, `star_count`) | none | all-time only | `/v2/repositories/{ns}/` | ecosyste.ms `docker_downloads_count` (images using a package) |
| Hugging Face | `huggingface.co/api/models/{id}?expand[]=downloads&expand[]=likes&expand[]=downloadsAllTime` | none | last 30 days + all-time | `/api/models?author={u}` (same for datasets, spaces) | no |
| VS Code Marketplace | `POST marketplace.visualstudio.com/_apis/public/gallery/extensionquery` | none, undocumented | all-time installs + trending | filterType 18 = publisher | no |
| Open VSX | `open-vsx.org/api/{ns}/{ext}` (`downloadCount`) | none | all-time | `open-vsx.org/api/{ns}` | no |
| Homebrew | `formulae.brew.sh/api/formula/{f}.json` (`analytics`) | none | 30/90/365-day installs | no (formulae are not owned by a user) | no |
| RubyGems | `rubygems.org/api/v1/gems/{g}.json` | none | all-time + current-version | `/api/v1/owners/{handle}/gems.json` | `/api/v1/gems/{g}/reverse_dependencies.json` |
| Packagist | `packagist.org/packages/{v}/{p}/stats.json`, `/stats/all.json?average=daily` | none | total/monthly/daily; daily series | `/packages/list.json?vendor={v}`; maintainer in package JSON | `dependents` in `/packages/{v}/{p}.json` |
| NuGet | `azuresearch-usnc.nuget.org/query?q=packageid:{id}` (`totalDownloads`) | none | all-time | `q=owner:{owner}` | no (deps.dev covers NuGet) |
| Go | no downloads exist; `pkg.go.dev/v1/imported-by/{path}` (`importedBy.total`) | none | snapshot | no | pkg.go.dev imported-by; deps.dev |
| Maven Central | no public download counts; `search.maven.org/solrsearch/select` metadata | none | n/a | by groupId | deps.dev |
| JSR | `api.jsr.io/scopes/{s}/packages/{p}/downloads` | none | 90 days daily, split by `jsr_meta` / `npm_tarball` | `/scopes/{s}/packages` | `dependentCount` in package JSON |

## 1. PyPI

### 1.1 pypistats.org

Endpoints (verified live): `GET https://pypistats.org/api/packages/{pkg}/recent[?period=day|week|month]`, `/overall[?mirrors=true|false]`, `/python_major[?version=3]`, `/python_minor[?version=3.12]`, `/system[?os=linux|darwin|windows|other]` [1]. No key. Responses carry `x-ratelimit-limit: 60` and `retry-after: 1`; the docs say only "IP-based rate limiting is imposed application-wide" [1].

History: the docs and about page say time series are retained for 180 days [1][2]. Live, `overall` for `requests` returned 217 daily rows per category (2026-04-08 to 2026-11-10), so the retention is at least 180 days but not exactly what is documented. Either way the daily series rolls off, so a weekly collector must accumulate it.

Mirrors: `overall` returns both `with_mirrors` and `without_mirrors`; the about page says aggregate stats "ignore known PyPI mirrors (such as bandersnatch) unless noted otherwise" [2]. For `dol` over the 30 days to 2026-11-10, with_mirrors = 113,926 and without_mirrors = 89,982 (verified live).

Breakdowns: `system` categories are Darwin, Linux, Windows, null, other; `python_minor` returns per-minor series including junk values such as `3.32` from spoofed user agents (verified live).

Caveat found live: `recent.last_week` and `recent.last_day` equal the sum of the `overall` without-mirrors series, but `recent.last_month` does not (`dol`: 41,593 versus 89,982 for the last 30 days; `requests`: 1.20 B versus 1.47 B). Use the daily `overall` series and sum it yourself. ecosyste.ms republishes the same `last_month` figure as its PyPI `downloads` (requests: 1,202,777,296 in both).

The site asks not to bulk-download every package and recommends BigQuery for heavy use [1].

### 1.2 pepy.tech

The JSON API requires a key in `X-API-Key` (verified: `{"message":"No API Key provided"}`, HTTP 401). The free plan allows 5 requests per minute sustained, burst 10, and the v2 project endpoint returns `total_downloads` plus 3 months of daily per-version data; longer history is on paid plans (1 to 5 years) [3]. Badges need no key: `https://static.pepy.tech/badge/{pkg}` and `https://static.pepy.tech/personalized-badge/{pkg}?period=total&units=none` return an SVG whose text holds the all-time total (requests: 40,232,323,158, verified live). Scraping the SVG is the only key-free way to get an all-time PyPI total; it is not a documented data API.

### 1.3 BigQuery `bigquery-public-data.pypi.file_downloads`

The table is fed by the Linehaul project, streaming PyPI download logs into BigQuery [4]. The BigQuery sandbox gives 1 TiB of query processing per month and 10 GiB lifetime storage without a credit card; sandbox tables expire after 60 days [5]. In CI it needs a Google Cloud project and a service-account JSON key stored as a secret, and the client is not stdlib (the REST API can be called with stdlib plus a signed JWT, which is real work). A full-table query is large; queries must filter on the partition column (`timestamp`) and project to stay inside 1 TiB (sizes unverified).

### 1.4 ClickHouse public PyPI dataset (ClickPy)

ClickPy's README documents a public read-only ClickHouse instance at `sql-clickhouse.clickhouse.com` with user `demo` and an empty password, with quotas applied (unspecified) [6]. Verified live: anonymous HTTP works with `curl 'https://sql-clickhouse.clickhouse.com/?user=demo' --data-binary 'SELECT ...'` (the `play` user also works). The `pypi` database has pre-aggregated tables: `pypi_downloads_per_day` (date, project, count), `pypi_downloads_per_day_by_version`, `..._by_installer_by_type`, `..._by_python`, `..._by_system`, `..._by_country`, `pypi_downloads_per_month`, and `projects` (package metadata). `dol` history runs from 2020-09-28 to 2026-11-10 (yesterday). Its last-30-day sum (113,999) matches pypistats `with_mirrors` (113,926), so it includes mirrors; filter by installer to exclude them.

This is the strongest key-free PyPI source: years of daily history, installer breakdown (pip, uv, poetry, bandersnatch, Browser, blank), stdlib `urllib` only. Risk: it is a vendor demo with undocumented quotas and no SLA, so treat it as a seam with pypistats as the fallback.

### 1.5 Listing a user's PyPI packages

- XML-RPC `user_packages(user)` returns `[role, package]` pairs (Owner/Maintainer). Verified live: 284 rows for `thorwhalen1`. The docs list it under "Deprecated Methods: still available, but going away", say "do not build new integrations against them", and warn of "a very restrictive rate limit" [7]. Other XML-RPC methods (`list_packages`, `package_releases`, `release_urls`, `release_data`) were disabled in September 2024 [8]. One call per run is fine; plan for its removal.
- `https://pypi.org/user/{u}/` now returns a JavaScript challenge page to non-browser clients (verified: zero `package-snippet` elements with either a bot or a browser User-Agent). HTML scraping is no longer viable from CI.
- The PyPI JSON API (`/pypi/{p}/json`) now carries an `ownership` object (`{"organization": null, "roles": [{"role": "Owner", "user": "thorwhalen1"}]}`, verified live), which confirms ownership per package but cannot enumerate. Its `info.downloads` fields are all `-1` (deprecated).
- ecosyste.ms `GET /api/v1/registries/pypi.org/maintainers/{u}/packages` returned 276 packages for `thorwhalen1` (verified live), close to XML-RPC's 284. Good fallback; slightly stale.
- Robust design: an explicit list or pattern in config, with XML-RPC, then ecosyste.ms, as discovery strategies.

## 2. npm

Download counts (verified live, no key): `GET https://api.npmjs.org/downloads/point/{last-day|last-week|last-month|YYYY-MM-DD:YYYY-MM-DD}/{pkg}` and `/downloads/range/{period}/{pkg}` (daily array). The docs say non-bulk queries return at most 18 months, bulk queries at most 365 days, data starts 2015-01-10, bulk takes up to 128 comma-separated packages but not scoped ones, and per-version counts exist only for the last 7 days via `/versions/{pkg}/last-week` (scoped names percent-encode the slash) [9]. Live checks matched: a 2023-2026 range was silently clamped to 2025-05-01..2026-11-01 (550 days); the earliest date returned 2015-01-10; `@types/node,react` in bulk returned `"scoped packages are not currently supported in bulk lookups"`. Data is processed once a day after UTC midnight [9]. No rate limit is documented; responses are Cloudflare-cached with `max-age=300`. Because 18 months back is always available, a weekly collector only needs to accumulate per-version counts (7 days) and anything older than 18 months.

What counts: the npm team defines a download as a successful tarball fetch from the registry, including automated fetches by mirrors and bots [10].

Listing a maintainer's packages (verified live):

- `GET https://registry.npmjs.org/-/v1/search?text=maintainer:thorwhalen1&size=250` returned 70 (the search `size` cap is 250 per page; paginate with `from`). Each result now includes `downloads.{weekly,monthly}` and a `dependents` count, so one search call yields a snapshot of counts and dependents for all packages.
- `GET https://registry.npmjs.org/-/user/thorwhalen1/package` returned 70 packages with access level; `/-/org/{org}/package` lists an org's packages (worked for `zodal`). These are undocumented web endpoints.
- `author:thorwhalen1` returned 69, so maintainer and author differ slightly.

## 3. crates.io

Endpoints (verified live): `GET https://crates.io/api/v1/crates/{c}` gives `downloads` (all-time) and `recent_downloads` (90 days). `GET /api/v1/crates/{c}/downloads` gives `version_downloads` (daily per version for the top versions) plus `meta.extra_downloads` (daily for the rest); both covered 2026-08-14 to 2026-11-11, that is 90 days. `GET /api/v1/crates/{c}/{version}/downloads` gives 90 days for one version. `GET /api/v1/crates/{c}/reverse_dependencies?per_page=1` gives `meta.total` (serde: 139,699).

Older history: daily CSVs exist at `https://static.crates.io/archive/version-downloads/{YYYY-MM-DD}.csv` (2024-01-01 returned 2 MB, verified), and a full database dump is published every 24 hours [11]. So 90 days is not a hard wall, but per-crate back-fill means downloading one CSV per day; accumulate weekly instead.

User listing (verified live): `GET /api/v1/users/{github_login}` returns the numeric id; `GET /api/v1/crates?user_id={id}&per_page=100` lists their crates with seek pagination (dtolnay: 234). `GET /api/v1/users/{id}/stats` returns `total_downloads`. Account `thorwhalen` exists on crates.io.

Policy: requests without a User-Agent get HTTP 403 with a message asking for a UA that identifies the bot, preferably with contact details (verified live). The data-access policy caps API crawling at 1 request per second and recommends the index or the daily dump for bulk [11][12]. Use a UA such as `pkgstats/<version> (+https://github.com/<repo>)`, no personal email.

Counting changes: since March 2024 downloads are counted from CDN logs, which raised counts mostly via previously uncounted mirror traffic and was not back-filled [13]; a later change (PR #12210, live by the January 2026 update) counts only requests from Cargo, removing the background floor of bot, scraper and mirror downloads [14][15]. Series that straddle late 2025 have a step down for small crates.

## 4. GitHub

Traffic (already known): views, clones, referrers and paths cover 14 days and need push access [16]; verified unauthenticated `traffic/views` returns 401.

Star history (verified live, no auth): GitHub announced on 2026-09-04 a privacy-safe star history endpoint after restricting stargazer listings to admins and collaborators [17]. The URL shape is `GET /repos/{owner}/{repo}/stargazers/history` with `per_page` (max 30) and `page` (max 100); it returns weekly buckets, newest first, each `{"week": <unix ts>, "total": n, "days": [Sun..Sat]}`, paging back to the repository's creation week; week and day boundaries are not guaranteed to be UTC [18]. Live: `psf/requests` returned 30 weeks on page 1 and `rel="last"` page 28 (about 16 years), unauthenticated at 60 requests per hour. Page max 100 times 30 weeks is about 57 years, so full history is reachable. Removed stars are not kept as events [17][19]. The old `/stargazers` list now returns 401 unauthenticated (verified), which broke star-history.com-style tools [19][20].

Dependents ("Used by"): no REST or GraphQL endpoint exists (unverified as an absence, but none found in docs or community answers). The count is in the HTML of `https://github.com/{o}/{r}/network/dependents` (verified: requests shows 4,263,493 repositories and 152,206 packages). Tools such as `github-dependents-info` scrape it [21]. It is fragile, rate-limited HTML; prefer registry-side dependents.

## 5. Cross-platform services

### 5.1 deps.dev

No auth (verified). `GET https://api.deps.dev/v3/systems/{npm|pypi|cargo|maven|go|nuget|rubygems}/packages/{name}` lists versions and marks the default one; `GET /v3/projects/github.com%2F{o}%2F{r}` gives stars, forks, open issues and OpenSSF Scorecard. Dependents are only in the alpha API: `GET /v3alpha/systems/{sys}/packages/{p}/versions/{v}:dependents` returns `dependentCount`, `directDependentCount`, `indirectDependentCount` [22]. Verified: left-pad 1.3.0 has 19,148; requests 2.32.5 has 2,551; guava 33.0.0-jre has 6,924; anyhow 1.0.104 (default) has 14,159 while anyhow 1.0.80 has 0; dol 0.3.120 has 173 while dol 0.3.100 has 0. Counts are attributed to the version dependents resolve to, so query the default version. Anomaly: serde 1.0.229 (default) returned 0, so cargo counts are not reliable for every crate. Go returned "dependents not found".

### 5.2 ecosyste.ms (packages.ecosyste.ms)

No key (verified). `GET https://packages.ecosyste.ms/api/v1/registries/{registry}/packages/{name}` returns `downloads` with `downloads_period` (`last-month` for PyPI and npm, `total` for crates.io), `dependent_packages_count`, `dependent_repos_count`, `docker_downloads_count`, `rankings` percentiles, `versions_count` and more (verified for requests, left-pad, serde). `GET /api/v1/registries/{registry}/maintainers/{login}/packages` lists a maintainer's packages (276 PyPI, 47 npm for thorwhalen1, so npm coverage lags the registry's 70); `/maintainers/{login}` gives `packages_count` and `total_downloads`. 117 registries are indexed, including conda-forge, anaconda.org, Docker Hub, Hugging Face, Homebrew, Open VSX, Go, NuGet, Maven, Packagist, RubyGems and CRAN (verified). No download time series.

Rate limits: the API page describes an anonymous "common pool" and a "polite pool" reached by adding `mailto=` or a `mailto:` User-Agent or a `From` header, without published numbers [23]. Observed headers: `x-ratelimit-limit: 5000` per hour, tier `anonymous` (one earlier call reported a 15,000 limit, tier `parlay`). Licence: APIs and data CC BY-SA 4.0, code AGPL-3 [23]. Derived dashboards that republish its data should attribute and share alike. The ecosyste.ms home page returns HTTP 402 "Payment Required" to browser-like User-Agents but 200 to a custom UA (verified), so send a descriptive UA.

### 5.3 libraries.io

Still online and fresh (dol's 2026-11-09 release was present, verified). Docs say every request needs a free `api_key` and allow 60 requests per minute [24]; live, keyless requests succeed with `x-ratelimit-limit: 10` per hour. It returns `dependents_count` and `dependent_repos_count` (requests: 112,450 and 57,895). The API page carries a banner about Sonar acquiring Tidelift [24]. ecosyste.ms (by libraries.io's original author; unverified) offers the same fields without a key at higher limits, so libraries.io is redundant.

## 6. Other platforms

- conda-forge / anaconda.org: `GET https://api.anaconda.org/package/{channel}/{pkg}` gives `ndownloads` (all-time; requests on conda-forge: 102,911,007) and per-file counts (verified). Time series come from Anaconda's public package-data bucket, monthly and hourly parquet files on S3 (`conda/monthly/2026/2026-10.parquet` is the latest, verified) [25]; parquet needs a non-stdlib reader. Listing a large channel with `/packages/{owner}` was too slow to complete in 120 s (conda-forge, bioconda).
- Docker Hub: `GET https://hub.docker.com/v2/repositories/{ns}/{repo}/` gives `pull_count` and `star_count` (library/python: 9.6 B pulls); `/v2/repositories/{ns}/` lists a namespace's repos (verified) [26]. All-time only; accumulate for trends.
- Hugging Face: `GET https://huggingface.co/api/models/{id}?expand[]=downloads&expand[]=likes&expand[]=downloadsAllTime` (verified: bert-base-uncased 31.4 M downloads, 3,067 likes, 3.29 B all-time); the model page labels `downloads` as "Downloads last month" (verified). `/api/models?author={u}`, `/api/datasets?author={u}` and `/api/spaces?author={u}` list a user's repos. Downloads are counted server-side on query files such as `config.json`, every GET and HEAD counts, and per-request logs with CI exclusion are a paid Publisher Analytics feature [27].
- VS Code Marketplace: undocumented `POST https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery` with header `Accept: application/json;api-version=7.2-preview.1`, `flags: 914`; returns `install`, `updateCount`, `downloadCount`, ratings and trending (verified for ms-python.python). `filterType: 18` with a publisher name lists that publisher's extensions (13 for ms-python). Unofficial; may change.
- Open VSX: `GET https://open-vsx.org/api/{namespace}/{extension}` gives `downloadCount`, ratings; `GET /api/{namespace}` lists extensions (verified) [28].
- Homebrew: `GET https://formulae.brew.sh/api/formula/{f}.json` has `analytics.install`, `install_on_request` and `build_error` for 30, 90 and 365 days; `/api/analytics/install/30d.json` covers all formulae (verified) [29]. Only relevant if the person maintains a formula; there is no owner concept.
- RubyGems: `GET https://rubygems.org/api/v1/gems/{g}.json` (all-time `downloads`, `version_downloads`), `/api/v1/owners/{handle}/gems.json`, `/api/v1/gems/{g}/reverse_dependencies.json` (verified; rails has 13,624 reverse deps) [30].
- Packagist: `GET https://packagist.org/packages/{vendor}/{pkg}.json` has `downloads.{total,monthly,daily}`, `favers`, `dependents`, `suggesters`, `github_stars`, maintainers; `/stats/all.json?average=daily&from=YYYY-MM-DD` gives a daily series; `/packages/list.json?vendor={v}` lists a vendor (verified) [31].
- NuGet: search service `GET https://azuresearch-usnc.nuget.org/query?q=packageid:{id}` returns `totalDownloads` and owners; `q=owner:{owner}` lists an owner's packages (verified) [32]. All-time only.
- Go: there are no download counts (the module proxy publishes none). pkg.go.dev answers JSON at `https://pkg.go.dev/v1/package/{path}` and `https://pkg.go.dev/v1/imported-by/{path}` (`importedBy.total`: google/uuid 113,457), verified live; documentation status of this API is unverified (tracking issue [33]).
- Maven Central: the search API gives metadata only (verified); download statistics are visible only to the publisher in the Central portal (unverified). deps.dev covers Maven dependents [34].
- JSR: `GET https://api.jsr.io/scopes/{scope}/packages/{pkg}` has `dependentCount` and `score`; `/downloads` gives 90 days of daily counts split into `jsr_meta` and `npm_tarball` (verified 2026-08-14 to 2026-11-11) [35].

Worth supporting after the core four: Hugging Face (key-free, a person's models and datasets, likes), conda-forge (Python users), Docker Hub, VS Code / Open VSX for extension authors, JSR for Deno/TS. RubyGems, Packagist and NuGet are each a single unauthenticated GET, so cheap to add as platform plugins if anyone needs them.

## 7. Websites a human can look at today

Liveness checked 2026-11-11 by HTTP status and page content:

- Alive: npm-stat.com (also a JSON API, `npm-stat.com/api/download-counts?package=...&from=...&until=...`, HTTP 200), npmtrends.com, npmcharts.com (redirects to www), pypistats.org, pepy.tech, clickpy.clickhouse.com, piptrends.com, lib.rs, star-history.com (switched to GitHub's new endpoint after the stargazer restriction [19]), deps.dev, packages.ecosyste.ms, libraries.io.
- OSS Insight: the site is up but rebranded around "AI Agent Analytics & Open Source GitHub Intelligence"; its public API call `api.ossinsight.io/v1/repos/psf/requests/stargazers/history/` returned an internal server error.
- Snyk Advisor: retired as a standalone site; `snyk.io/advisor/...` URLs 301-redirect to `security.snyk.io/package/...`, which keeps the popularity and health cards [36][37]. Snyk's developer page announced the sunset for January 2026 (secondary report).
- Socket.dev: up but behind a Cloudflare bot challenge (403 to curl), so usable by a human only.
- ecosyste.ms home page: returns 402 to browser-like clients from this network (sub-sites fine).

## 8. Engagement versus noise

Downloads are mostly machines. On npm, Tenable measured that every newly published version receives about 100 to 150 downloads from mirrors and analysis bots (135 to 158 in their controlled test), and an attacker reached about 50,000 downloads in three days by publishing 724 versions [38]. Fetching a tarball URL directly also inflates counts (17,000 in an hour in Tenable's reproduction; first shown by Richardson in 2021) [38][39], and Safety reported a malicious package showing about 4.5 M weekly downloads with no plausible users [40]. ReversingLabs calls the technique "download pumping" [41]. For a small package, release cadence alone sets a floor: a maintainer who publishes often sees counts that track releases, not users.

On PyPI, mirrors, CI and scanners dominate small packages. Alex Gaynor noted in 2014 that CI servers inflate counts and that downloads are not users [42]. The `pypi-real-downloads` tool's worked example found only 3.0% of one package's 30-day downloads could have been a person: 48.3% sent no installer header, 20.4% were browsers, the rest mirrors and bots [43]; one package, not a general rate. Own measurement via ClickHouse for `dol`, last 30 days: pip 51,386, uv 30,434, blank installer 15,296, bandersnatch 8,647, Browser 5,059, `requests` library 2,439, poetry 653, Nexus 80; about 28% of the total is certainly not an installer, and pip/uv traffic still includes CI. Usable signals: the without-mirrors series, the installer mix, and the OS mix (Linux-heavy means CI and servers; Darwin and Windows lean towards developers).

On crates.io the registry itself now filters to Cargo user agents because bots created a constant floor on unpopular crates [14][15]. Hugging Face counts every GET or HEAD on a query file and sells deduplicated, CI-excluding logs separately [27].

Stars can be bought. He et al. found about 4.5 million suspected fake stars on GitHub from 2019 to 2024, with campaigns touching 15.84% of repositories with at least 50 stars in the July 2024 peak, and fake stars hurting real growth after two months [44]. Star history is a trend signal, not proof of use.

Signals considered meaningful adoption:

- Dependents. Other packages declaring a dependency is the core input of criticality work: the OpenSSF Criticality Score uses dependent counts [45], the Linux Foundation critical-projects effort lists downstream dependents and downloads as candidate signals and warns that inconsistently measured signals bias rankings [46], and the OpenSSF comparison notes dependents only see open-source consumers [47]. Use deps.dev (direct versus indirect), ecosyste.ms (`dependent_packages_count`, `dependent_repos_count`), npm search `dependents`, crates.io `reverse_dependencies`, RubyGems reverse deps, Packagist `dependents`, pkg.go.dev imported-by.
- Version adoption: the share of downloads on recent versions (npm last-week per version, ClickHouse by-version for PyPI, crates.io per-version) shows real upgraders; bots spread evenly over new releases.
- People, not machines: GitHub unique visitors and unique cloners (traffic API, 14 days, needs accumulation), issues and PRs opened by non-owners, forks with commits, and referrers.
- Stars and likes over time (GitHub star history, HF likes, Packagist favers), read as trends and checked against the rest.
- Download distribution: installer, OS and Python version mixes and the without-mirrors series on PyPI; per-version shape on npm; Cargo-only counts on crates.io.

Design consequence: report downloads with their noise floor and context (release dates, installer mix) and put dependents, non-owner activity, unique visitors and version adoption up front as the engagement signals.

## REFERENCES

1. [pypistats.org API documentation](https://pypistats.org/api/)
2. [pypistats.org About](https://pypistats.org/about)
3. [pepy.tech API documentation](https://pepy.tech/pepy-api)
4. [PyPI docs: BigQuery datasets](https://docs.pypi.org/api/bigquery/)
5. [Google Cloud: BigQuery sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox)
6. [ClickHouse/clickpy README](https://github.com/ClickHouse/clickpy)
7. [PyPI XML-RPC API reference](https://dev.pypi.org/api-reference/xml-rpc/)
8. [Deprecation of PyPI XMLRPC methods (discuss.python.org)](https://discuss.python.org/t/deprecation-of-pypi-xmlrpc-methods/63026)
9. [npm registry docs: download counts](https://github.com/npm/registry/blob/main/docs/download-counts.md)
10. [npm blog: numeric precision matters, how npm download counts work (2014)](https://blog.npmjs.org/post/92574016600/numeric-precision-matters-how-npm-download-counts-work.html)
11. [crates.io data access policy](https://crates.io/data-access)
12. [RFC 3463: crates.io policy update](https://rust-lang.github.io/rfcs/3463-crates-io-policy-update.html)
13. [Rust blog: crates.io download changes (2024-03-11)](https://blog.rust-lang.org/2024/03/11/crates-io-download-changes/)
14. [Rust blog: crates.io development update (2026-01-21)](https://blog.rust-lang.org/2026/01/21/crates-io-development-update)
15. [rust-lang/crates.io PR #12210: count only Cargo downloads](https://github.com/rust-lang/crates.io/pull/12210)
16. [GitHub REST docs: repository traffic](https://docs.github.com/en/rest/metrics/traffic)
17. [GitHub changelog: new API endpoint provides privacy-safe star history data (2026-09-04)](https://github.blog/changelog/2026-09-04-new-api-endpoint-provides-privacy-safe-star-history-data/)
18. [GitHub REST docs: get repository star history](https://docs.github.com/rest/activity/starring?apiVersion=2026-03-10#get-repository-star-history)
19. [star-history.com: GitHub has restricted access to star data](https://www.star-history.com/blog/github-stargazer-api-restriction/)
20. [GitHub community discussion #201209: impacts of removing /stargazers](https://github.com/orgs/community/discussions/201209)
21. [github-dependents-info on PyPI](https://pypi.org/project/github-dependents-info/)
22. [deps.dev API v3alpha documentation](https://docs.deps.dev/api/v3alpha/)
23. [ecosyste.ms API overview (rate limits, licence)](https://ecosyste.ms/api)
24. [libraries.io API documentation](https://libraries.io/api)
25. [anaconda/anaconda-package-data](https://github.com/anaconda/anaconda-package-data)
26. [Docker Hub API reference](https://docs.docker.com/reference/api/hub/latest/)
27. [Hugging Face Hub: models download stats](https://huggingface.co/docs/hub/models-download-stats)
28. [Open VSX registry API (Swagger)](https://open-vsx.org/swagger-ui/index.html)
29. [Homebrew analytics documentation](https://docs.brew.sh/Analytics)
30. [RubyGems.org API guide](https://guides.rubygems.org/rubygems-org-api/)
31. [Packagist API documentation](https://packagist.org/apidoc)
32. [NuGet search query service API](https://learn.microsoft.com/en-us/nuget/api/search-query-service-resource)
33. [golang/go issue 36785: x/pkgsite API](https://go.dev/issue/36785)
34. [Maven Central search REST API guide](https://central.sonatype.org/search/rest-api-guide/)
35. [JSR API documentation](https://jsr.io/docs/api)
36. [Snyk update: Snyk Advisor insights are now part of security.snyk.io](https://updates.snyk.io/snyk-advisor-insights-are-now-part-of-security-snyk-io)
37. [Snyk blog: Snyk Advisor and the security database](https://snyk.io/blog/snyk-advisor-security-database/)
38. [Tenable: download pumping, a new npm deception technique (2026-05-28)](https://tenable.com/blog/how-cyberattackers-inflate-malicious-package-npm-download-counts)
39. [Andy Richardson: how I exploited npm downloads and why you shouldn't trust them](https://dev.to/andyrichardsonn/how-i-exploited-npm-downloads-and-why-you-shouldn-t-trust-them-4bme)
40. [Safety: Russian hackers manipulate npm to make realistic packages](https://safetycli.com/research/russian-hackers-manipulate-npm-to-make-realistic-packages)
41. [ReversingLabs: download pumping joins the trust-abuse bandwagon](https://www.reversinglabs.com/blog/download-pumping-trust-abuse)
42. [Alex Gaynor: PyPI download statistics (2014)](https://alexgaynor.net/2014/jan/03/pypi-download-statistics/)
43. [pypi-real-downloads on PyPI](https://pypi.org/project/pypi-real-downloads/)
44. [He et al.: 4.5 Million (Suspected) Fake Stars in GitHub (arXiv:2412.13459)](https://arxiv.org/abs/2412.13459)
45. [ossf/criticality_score](https://github.com/ossf/criticality_score)
46. [linuxfoundation/critical-projects](https://github.com/linuxfoundation/critical-projects)
47. [OpenSSF: Apples and apples? Comparing approaches to measuring criticality and risk](https://openssf.org/blog/2022/12/08/apples-and-apples-comparing-approaches-to-measuring-criticality-and-risk-at-the-openssf/)
