# Environment Foundation — Design

- **Date:** 2026-09-29
- **Status:** Approved in conversation, pending written-spec review
- **Scope:** Initial setup of the `data-engineering-lab` monorepo and Claude's core files. No data projects yet.

## 1. Intent

A long-lived workspace where Tomas and Claude build data engineering projects together.

- **Purpose:** learning/expertise + public portfolio.
- **Clouds:** multi-cloud by design (GCP, AWS, Azure, Databricks, ...). Nothing in the foundation may assume a single cloud.
- **Roles:** Claude is the primary executor *and* explains the why (decisions, alternatives, theory) so Tomas can replicate and transfer it.
- **Language:** chat in Spanish; code, commits, READMEs, ADRs in English; `docs/learnings/` in Spanish.

**Success criteria**
1. A new project can be started by copying `projects/_template/` and runs `uv run pytest` green out of the box.
2. No secret can reach a commit without gitleaks flagging it.
3. Claude, in a fresh session, knows its role, conventions and the repo map from `CLAUDE.md` alone.
4. The repo is pushed to GitHub (`TomasRipsky/data-engineering-lab`, private) on branch `main`.

## 2. Approach

**Minimal core that grows on demand (approach A).** Only create what is used from day one. Shared libraries, per-cloud infra folders, CI workflows and local data stacks are added when a real project needs them — and extracted to `shared/` only once two projects duplicate the same thing.

Rejected:
- *Full scaffolding upfront* — dead code and premature decisions; empty cloud folders hurt a portfolio.
- *uv workspace at root* — couples projects; makes extracting one to its own repo harder.

## 3. Repository layout

```
data-engineering-lab/
├── CLAUDE.md                  # Claude's core instructions (EN, < ~120 lines)
├── README.md                  # Portfolio front page + project index
├── .claude/settings.json      # Shared plugins + permissions
├── projects/
│   └── _template/             # Skeleton for new projects
│       ├── README.md          # Sections: overview, architecture, run, what I learned
│       ├── pyproject.toml     # uv-managed, ruff + pytest configured
│       ├── src/<package>/__init__.py
│       ├── tests/test_smoke.py
│       ├── docs/decisions/    # Project-level ADRs
│       ├── .env.example
│       └── Makefile           # setup / test / lint / destroy (destroy = no-op placeholder in template)
├── docs/
│   ├── adr/                   # Environment-level ADRs (0001 monorepo, 0002 python tooling)
│   ├── learnings/             # Concept notes in Spanish
│   └── superpowers/           # Specs and plans
├── .gitignore                 # Python, env files, OS files, cloud credentials, data/
├── .editorconfig
└── .pre-commit-config.yaml    # gitleaks + ruff (lint + format) + basic hygiene hooks
```

Each project is **self-contained**: own `pyproject.toml`, own `uv.lock`, own README. It can be extracted to a standalone repo without untangling anything.

## 4. `CLAUDE.md` contents

1. **Identity & role** — senior data engineer; executor + mentor.
2. **Language rules** — as in §1.
3. **Repo map** — what lives where; how to start a project (copy `_template`, rename package, add to root README index).
4. **Mentor protocol** — after meaningful work, close with a short *Why* block (decision → alternatives → underlying concept). Durable decisions become ADRs; new concepts become a `docs/learnings/` note.
5. **Conventions** — Python via uv, ruff, pytest; SQL lowercase with CTEs; Terraform per cloud inside each project (`projects/<p>/infra/<cloud>/`); Conventional Commits; branches `feat/<project>-<topic>`.
6. **Security & cost** — never commit secrets (only `.env.example`); gitleaks pre-commit; cloud labs use free tier first, budget alerts, and a documented `make destroy`.
7. **Definition of Done** — tests green, project README with architecture diagram, run instructions and "What I learned".

## 5. Tooling

Installed via Homebrew (approved): `uv`, `ruff`, `pre-commit`, `gitleaks`, `duckdb`.
Deferred until a project needs them: Java/Spark, dbt, AWS CLI, Azure CLI, Node.

Git: branch renamed `master` → `main`; `gh` switched to HTTPS with its credential helper (done).

## 6. Out of scope

- CI workflows (added with the first project that has real tests).
- `shared/` library, root docker-compose stack, per-cloud infra.
- Importing existing repos (`marineflow`, `citypulse_analytics`) — separate decision later.

## 7. Verification

- `pre-commit run --all-files` passes.
- A planted fake secret in a scratch file is blocked by gitleaks (then removed).
- `cd projects/_template && uv run pytest` passes; `uv run ruff check .` passes.
- `gh repo view TomasRipsky/data-engineering-lab` shows the pushed `main` branch.
