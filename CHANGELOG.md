# Changelog

All notable changes to this repository are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

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
