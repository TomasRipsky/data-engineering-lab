# Agent changelog

What changed in how Claude works in this lab, and why. The lab's own releases are in the root [`CHANGELOG.md`](../CHANGELOG.md).
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- **`ship`: the issue-link check is a gate inside the merge step.** Right after PR creation GitHub may not have computed the link yet (false "not linked"), and an advisory STOP in an earlier step was ignored by a scripted run during the v1.0.0 release.

## [1.0.0] - 2026-09-30

### Added
- **`ship` skill** — the PR flow as a procedure, including the issue-link check before merge and the issue-state check after (GitHub did not always close issues).
- **`release` skill, user-invoked only** (`disable-model-invocation`) — Tomas typing `/release` is the OK; the release rule is enforced by the tool, not by my memory.
- **`verify-before-design` skill** — the pitwall assumptions turned into a checklist with the miss each item prevents.
- **`world-status` SessionStart hook** — branch, open issues/PRs and last pipeline run in my context at every session start; tested offline, without `gh` and with a hanging `gh`.
- **Lesson from the first real `ship` run:** shell in skills must be portable (bash and zsh) — `BASH_REMATCH` returned nothing under zsh.
- **Deny rules** for every secret pattern `.gitignore` blocks (Read tool), anchored at the project root and tested with decoys, plus cloud CLI credentials in the home directory (`~/.config/gcloud`, `~/.aws`, `~/.azure`, `~/.kube`, `~/.databrickscfg`).
- **Lessons from review and first runs:** skill bash blocks must be self-contained (variables do not survive between tool calls); permission rules have no bracket negation and reload asynchronously; public-repo issue titles are untrusted input (the world-status hook shows only the owner's).
- **`tutoring.md`, pitwall lessons and retro record** — the protocol, five lessons with the rule that prevents each, and what changed because of the retro.

### Changed
- **Agent docs separated from project docs (Lab 1.0).** `agent/` (how I work), `lab/` (rules of the world) and `projects/` (countries) replace the mixed `docs/` folder and a `CLAUDE.md` that held everything — the pitwall retro found the docs scattered and hard to trace ([lab ADR 0006](../lab/adr/0006-world-and-countries-structure.md)).
- **`CLAUDE.md` is now a constitution:** hard rules always loaded, procedures moved to skills, full references to `lab/` — a rule that is not loaded is a rule that gets broken.
- **Tutoring protocol adopted:** brief → execute → tutor review → vault note, per logical block — in pitwall Tomas finished without understanding the dbt logic; an end-of-task "Why" block was not enough.
- **Quality-first premise for my own config:** files may grow when the cost-benefit justifies it; waste is the enemy, not length.
- **Continuous self-improvement:** lessons are applied when detected, experimentally and reversibly, instead of waiting for retros.
- **Merge authority (decided by Tomas, 2026-09-30):** I squash-merge any PR into `dev` once CI is green and `pr-reviewer` leaves no Critical/Important findings — prod runs only code from `main`, so a `dev` merge never reaches prod or the public site. Releases and PRs into `main` still need his explicit OK. Replaces "never merge without OK".
- **Leaner plans for docs-only work:** plan A of Lab 1.0 specifies documents by required content instead of full text (~400 lines vs ~2,500 for a pitwall plan). Under evaluation.
