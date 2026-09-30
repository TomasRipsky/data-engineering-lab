# 0006 — World and countries structure

- **Status:** Accepted
- **Date:** 2026-09-30

## Context
The pitwall retro found the docs scattered: lab and project specs mixed under `docs/superpowers/`, Claude's working rules and the lab's conventions mixed in one `CLAUDE.md`, and no obvious place for "how does this project work inside". The lab must scale to many projects, stay traceable, and make visible how an engineer works with an AI teammate — the repo is public and part of a portfolio.

## Decision
The repo is **the world**; each project is an independent **country**.

- `README.md` — world map. `CLAUDE.md` — Claude's always-loaded constitution (hard rules, tutoring summary, Definition of Done, where things live).
- `agent/` — how Claude works and how it has evolved (README, tutoring, lessons, retros, CHANGELOG).
- `lab/` — the rules of the world: `conventions.md`, `security-and-cost.md`, `tech-radar.md`, `adr/`, and lab-level specs and plans in `design/`.
- `projects/<p>/` — `README.md` (what, run, cost, learned), `docs/guide.md` (how it works inside), `docs/design/` (its specs and plans), `docs/decisions/` (its ADRs).
- `site/` — the public showcase (ADR 0005). `.claude/` — machinery only (skills, agents, hooks, settings).

Every question has exactly one place (table in `lab/conventions.md`). `CLAUDE.md` keeps the rules Claude must never forget; step-by-step workflows live as skills, not as prose to remember. There is no `agent/workflows/`: Claude Code loads skills only from `.claude/skills/`, and a second copy would drift.

## Alternatives considered
- Everything under `docs/` (`docs/lab/`, `docs/agent/`) — the GitHub convention and fewer moves, but it hides the agent's operating model, which is part of what the portfolio shows.
- Two repositories (agent environment vs projects) — breaks ADR 0001 (monorepo) and the traceability between retros and projects.

## Consequences
- Specs and plans executed before this change keep the old `docs/...` paths in their text: they are records and are not rewritten.
- Superpowers skills default to `docs/superpowers/`; `CLAUDE.md` overrides the location.
- ruff skips specs and plans (`extend-exclude = ["docs/design"]` in each project's ruff config, plus a pre-commit exclude for `lab/design/`): ruff formats Python blocks inside Markdown with the nearest project's settings, which would rewrite records.
- New projects get the layout from `projects/_template/` through the `new-project` skill.
