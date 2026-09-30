# Changelog

All notable changes to this repository are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- `pitwall`: CI (lint, tests, terraform validate, dbt in per-PR datasets) and a scheduled/manual pipeline via Workload Identity Federation; production environment backfilled 2023 → 2026.
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
