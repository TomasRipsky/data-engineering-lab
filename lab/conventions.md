# Conventions

How work is done in this lab and in every project repository built from it (lab ADR 0007: one repository per project, the lab is the base). `CLAUDE.md` holds the hard rules Claude always loads; this file is the full reference for humans. The step-by-step workflows also exist as Claude skills in `.claude/skills/`.

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

**Commits** — [Conventional Commits](https://www.conventionalcommits.org/). In the lab the scope is `lab`, or `agent` for changes to Claude's own system (skills, agents, hooks, `agent/`). In a project repository the scope is the component (`feat(dbt): ...`, `fix(infra): ...`) or omitted — the repository already names the project.

**Every repository** has the same shape: `dev` (default) and `main`, both protected by rulesets (PR required; squash into `dev`, merge commits into `main`), `type:*` labels, issue and PR templates. `new-project` sets this up.

**Releases** — Tomas runs `/release X.Y.Z` (the `release` skill, user-invoked only) for the lab or for a project. Each repository is versioned on its own with SemVer and a [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) `CHANGELOG.md`.
1. Branch `chore/<issue#>-release-vX.Y.Z` from `dev`, move `[Unreleased]` → `[X.Y.Z] - <date>` in `CHANGELOG.md` (and `agent/CHANGELOG.md` in the lab), PR into `dev`.
2. PR `dev → main` titled `release: vX.Y.Z`, merged with a **merge commit** (not squash), so `main` keeps the release boundaries.
3. `gh release create vX.Y.Z --target main`.

Releases and PRs into `main` need Tomas's explicit OK.

## Python

- `uv` for environments and dependencies (`uv.lock` committed per project), `ruff` for lint and format, `pytest` for tests.
- Python ≥ 3.12. Each project has its own `pyproject.toml` in its own repository.
- One test per clause of a behaviour (*every* vs *some*, empty input, required vs optional), each shown to bite: break the guarded line once and watch that test go red.
- A check on the shape of external data is verified against the oldest data the pipeline loads (one live request per old season or partition), not only against the recorded fixtures.

## SQL

- Lowercase keywords.
- CTEs over nested subqueries.
- One model = one grain, and the grain is stated (model description or header comment).

## Terraform

- One root module per cloud per project: `infra/<cloud>/` in the project repository.
- Remote state only when state is shared.
- Extract a shared module only when two projects duplicate the same infrastructure — as its own repository or package, not a folder in the lab.

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
| What does a new project start as? | `template/` |
| Which projects exist, where is each site? | `README.md` Projects table, `site/index.html` (the hub) |
| What does a project do, how do I run it? | the project repository's `README.md` |
| How does it work inside? | its `docs/guide.md` |
| Why did we decide X (project)? | its `docs/decisions/` |
| How was it designed and planned? | `lab/design/` (lab) or the project's `docs/design/` |

Specs and plans are records: once executed they are not rewritten, even when paths change later.
