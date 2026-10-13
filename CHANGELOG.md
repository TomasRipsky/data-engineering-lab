# Changelog

All notable changes to this repository are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Showcase site standard** ([lab ADR 0008](lab/adr/0008-showcase-site-standard.md)): every project is shown with a story page and a BI page. `template/site/` now carries the shared skeleton (`lab.css`, `lab.js`), a neutral theme, working story and BI page stubs and the rules; `lab/conventions.md` has the section.

### Changed
- The hub's pitwall redirects point straight at the sections of pitwall's new one-page site.

## [2.0.0] - 2026-10-13

### Changed
- **One repository per project; the lab is the base** ([lab ADR 0007](lab/adr/0007-one-repository-per-project.md), superseding ADRs 0001 and 0005). `pitwall` moved with its history to [TomasRipsky/pitwall](https://github.com/TomasRipsky/pitwall): its code, infrastructure, docs, CI/CD and dashboard now live and are released there. This repository's history and the tags v0.1.0–v1.0.0 still contain it.
- `projects/_template/` became [`template/`](template/): a complete standalone repository (git hygiene, issue and PR templates, Dependabot, a `ci` workflow, changelog, a `CLAUDE.md` pointer to the lab and a site skeleton with the shared look).
- The lab site is a static portfolio hub (`site/index.html`, deployed by `lab-site` on pushes to `main`): one card per project — pitwall, CityPulse, MarineFlow — each linking to the project's own site.

### Added
- Redirects from the old dashboard URLs (`/data-engineering-lab/pitwall/…`) to https://tomasripsky.github.io/pitwall/.

### Removed
- `projects/pitwall/`, the `pitwall-ci` and `pitwall-pipeline` workflows, the Observable Framework site and its npm dependencies. A release of the lab no longer touches any production system.

## [1.0.0] - 2026-09-30

### Changed
- Repo restructured into the world (`lab/`, `agent/`) and countries (`projects/`) model: lab ADRs and designs live in `lab/`, project specs and plans in `projects/<p>/docs/design/`, and `docs/` is gone ([lab ADR 0006](lab/adr/0006-world-and-countries-structure.md)).
- `CLAUDE.md` rewritten as a short constitution of hard rules; `README.md` is now the world map.
- ruff skips specs and plans (`extend-exclude` in each project's ruff config and a root `ruff.toml`): they are records, not code.

### Added
- Agent operating model ([`agent/`](agent/)): `ship`, `release` (user-invoked only) and `verify-before-design` skills; a session-start world-status hook with regression tests; deny rules for every secret pattern `.gitignore` blocks; the tutoring protocol; pitwall lessons and retro record.
- `lab/conventions.md`, `lab/security-and-cost.md` and `lab/tech-radar.md`.
- `agent/`: how Claude works in the lab, its changelog and its lessons.
- Project template: `docs/guide.md` (how it works inside) and `docs/design/`; `new-project` checks that the chosen stack is industry-standard.

## [0.4.0] - 2026-09-30

### Added
- Lab site (`site/`, Observable Framework on GitHub Pages): landing page, shared structure and a per-project data export contract (ADR 0005).
- `pitwall`: public race-strategy section with its own pit-wall look — stint timelines with Safety Car shading, fuel-corrected tyre wear, undercut success — rebuilt by the pipeline from prod through a read-only account (ADR 0007).

## [0.3.0] - 2026-09-30

### Added
- `pitwall`: CI (lint, tests, terraform validate, dbt in per-PR datasets) and a scheduled/manual pipeline via Workload Identity Federation; production environment (dev/prod GitHub Environments, prod runs released code from `main`).
- `pitwall`: dbt project (staging → intermediate → marts) with tyre degradation, pit stops and undercut detection; unit-tested racing rules; data-quality rules on raw data with failing rows stored in an `audit` dataset.
- `pitwall`: GCP dev environment (Terraform, WIF, query quota, budget) and `pitwall load` rebuilding BigQuery raw tables from the lake.
- `pitwall`: OpenF1 extractor (`pitwall ingest`) writing contract-checked Parquet to a raw lake, idempotent per Grand Prix.
- `pr-reviewer` agent: data-engineering-focused PR review before merges; read-only enforced by a tested Bash allowlist hook.

## [0.2.0] - 2026-09-29

### Added
- Project-scoped Context7 MCP (`.mcp.json`) for up-to-date library and cloud docs.

### Changed
- `dev` is now the default branch so `Closes #n` auto-closes issues on merge.
- Release recipe clarified (CHANGELOG via PR, `gh release create --target main`).

### Fixed
- Nested `data/` folders are no longer git-ignored; more secret file shapes are ignored.
- `/new-project`: fails fast on `gh` errors, stricter name validation, portable `perl` rename, fills placeholders, versions the vault note.
- Claude can read `.env.example` again; real `.env` files stay denied.
- `pre-commit install` documented for fresh clones.

## [0.1.0] - 2026-09-29

### Added
- Lab foundation: repo hygiene, pre-commit (gitleaks + ruff), uv project template.
- Claude operating manual (`CLAUDE.md`) and lab ADRs 0001–0004.
- GitHub workflow: protected `main`/`dev`, issue and PR templates, labels.
- `/new-project` skill.
