# 0001 — Monorepo with self-contained projects

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
We will build many projects over years, for learning and a public portfolio, across multiple clouds. Claude needs shared context (conventions, templates, decisions) in one place.

## Decision
One repository. Each project lives in `projects/<name>/` with its own `pyproject.toml`, lockfile, README and decisions, so it can be extracted to a standalone repo without untangling anything. Shared code is extracted to `shared/` only when two projects duplicate it.

## Alternatives considered
- **Hub repo + one repo per project** — cleaner per product, but conventions and context drift across repos and Claude loses shared context.
- **uv workspace at the root** — consistent dependencies, but couples projects and complicates extraction.
- **Full scaffolding upfront** (per-cloud infra folders, shared lib, CI) — dead code and premature decisions.

## Consequences
Easy reuse and one place to learn from. Root README must stay a clear index. CI (when added) must scope jobs to changed projects.
