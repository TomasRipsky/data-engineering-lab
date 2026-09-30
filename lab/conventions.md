# Conventions

How work is done in this lab. `CLAUDE.md` holds the hard rules Claude always loads; this file is the full reference for humans. The step-by-step workflows also exist as Claude skills in `.claude/skills/`.

## Git workflow

**Branches**
- `main` — released history. Protected: no direct pushes.
- `dev` — stable integration and the **default branch**. Protected: no direct pushes.
- Work branches come from `dev`: `<type>/<issue#>-<slug>`, with `<type>` one of `feat fix docs refactor test chore ci infra`.

**From issue to merge**
1. Every change starts from a GitHub **issue**.
2. Branch from `dev`, commit, push, open a PR into `dev` whose body says `Closes #n`.
3. Non-trivial PRs (new pipeline, SQL model, infra, dependency or workflow change) are reviewed by the `pr-reviewer` agent (`.claude/agents/`) on the checked-out branch; Critical and Important findings are fixed before merging. Its Bash is hook-restricted to read-only commands.
4. PRs are **squash-merged**. After merging, check that the issue actually closed — GitHub does not always link `Closes #n`.

**Commits** — [Conventional Commits](https://www.conventionalcommits.org/) with a scope: the project name (`feat(pitwall): ...`), `lab` for lab-level changes, or `agent` for changes to Claude's own system (skills, agents, hooks, `agent/`).

**Releases** — the lab is versioned with SemVer and a [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) `CHANGELOG.md`.
1. Branch `chore/<issue#>-release-vX.Y.Z` from `dev`, move `CHANGELOG.md` `[Unreleased]` → `[X.Y.Z] - <date>`, PR into `dev`.
2. PR `dev → main` titled `release: vX.Y.Z`, merged with a **merge commit** (not squash), so `main` keeps the release boundaries.
3. `gh release create vX.Y.Z --target main`.

Releases and PRs into `main` need Tomas's explicit OK.

## Python

- `uv` for environments and dependencies (`uv.lock` committed per project), `ruff` for lint and format, `pytest` for tests.
- Python ≥ 3.12. Each project has its own `pyproject.toml`; there is no root workspace (lab ADR 0001).

## SQL

- Lowercase keywords.
- CTEs over nested subqueries.
- One model = one grain, and the grain is stated (model description or header comment).

## Terraform

- One root module per cloud per project: `projects/<p>/infra/<cloud>/`.
- Remote state only when state is shared.
- Extract to `shared/` only when two projects duplicate the same infrastructure.

## Configuration

- Configuration comes from environment variables; `.env.example` documents them and is the only env file committed.
- Library and cloud APIs change fast: check the current docs (Context7 MCP, `.mcp.json`) before relying on memory.

## Docs — one question, one place

| Question | Place |
|---|---|
| What is this, how do I navigate? | `README.md` |
| What must Claude always do? | `CLAUDE.md` |
| How does Claude work, how has it evolved? | `agent/` |
| Rules of the world | `lab/conventions.md`, `lab/security-and-cost.md` |
| Why did we decide X (lab)? | `lab/adr/` |
| Which tech are we watching or avoiding? | `lab/tech-radar.md` |
| What does a project do, how do I run it? | `projects/<p>/README.md` |
| How does it work inside? | `projects/<p>/docs/guide.md` |
| Why did we decide X (project)? | `projects/<p>/docs/decisions/` |
| How was it designed and planned? | `lab/design/` (lab) or `projects/<p>/docs/design/` (project) |

Specs and plans are records: once executed they are not rewritten, even when paths change later.
