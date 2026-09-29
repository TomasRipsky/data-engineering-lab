# Environment Foundation — Design

- **Date:** 2026-09-29
- **Status:** Revision 2 — approved in conversation, pending written-spec review
- **Scope:** Initial setup of the `data-engineering-lab` monorepo, the Git workflow, Claude's identity and long-term memory, and the Obsidian second brain. No data projects yet.

## 1. Intent

A long-lived workspace where Tomas and Claude build data engineering projects together, and where Claude improves over time as a teammate.

- **Purpose:** learning/expertise + public portfolio.
- **Clouds:** multi-cloud by design (GCP, AWS, Azure, Databricks, ...). Nothing in the foundation may assume a single cloud.
- **Roles:** Claude is the primary executor *and* mentor — it explains the why (decisions, alternatives, theory) so Tomas can replicate, explain and transfer it. Tomas's ideas are open to debate.
- **Language:** chat in Spanish; code, commits, READMEs, ADRs and the second brain in English.
- **Efficiency:** tokens are a scarce resource. The system must get *better, not bigger*.

**Success criteria**
1. A new project can be started with `/new-project` and its template runs `uv run pytest` green out of the box.
2. No secret can reach a commit without gitleaks flagging it.
3. `main` and `dev` on GitHub reject direct pushes; every change reaches them through a PR.
4. Every change is traceable: issue → branch → commits → PR → release.
5. Claude, in a fresh session, knows its identity, conventions and the repo map from `CLAUDE.md` alone, and its learned preferences from memory.
6. The second brain lives in a stable location, is versioned privately, and Claude can read/write it.

## 2. Approach

**Minimal core that grows on demand (approach A).** Only create what is used from day one. Shared libraries, per-cloud infra folders, CI workflows, custom agents and local data stacks are added when a real need appears — and extracted to `shared/` only once two projects duplicate the same thing.

Rejected:
- *Full scaffolding upfront* — dead code and premature decisions; empty cloud folders hurt a portfolio.
- *uv workspace at root* — couples projects; makes extracting one to its own repo harder.

## 3. Repository layout

```
data-engineering-lab/                 # GitHub: TomasRipsky/data-engineering-lab (public)
├── CLAUDE.md                         # Claude's identity + operating manual (EN, < ~150 lines)
├── README.md                         # Portfolio front page + project index
├── CHANGELOG.md                      # Updated on each release (dev → main)
├── .claude/
│   ├── settings.json                 # Plugins, permissions, additionalDirectories (vault)
│   └── skills/new-project/SKILL.md   # The only custom skill for now
├── .github/
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/{feature,bug,learning}.md
├── projects/
│   └── _template/
│       ├── README.md                 # Overview, architecture, run, what I learned (links to vault)
│       ├── pyproject.toml            # uv-managed, ruff + pytest configured
│       ├── src/<package>/__init__.py
│       ├── tests/test_smoke.py
│       ├── docs/decisions/           # Project-level ADRs
│       ├── .env.example
│       └── Makefile                  # setup / test / lint / destroy
├── docs/
│   ├── adr/                          # Environment ADRs: 0001 monorepo, 0002 python tooling,
│   │                                 # 0003 branching model, 0004 memory architecture
│   └── superpowers/                  # Specs and plans
├── .gitignore  .editorconfig
└── .pre-commit-config.yaml           # gitleaks + ruff (lint + format) + hygiene hooks
```

`docs/learnings/` is dropped: the Obsidian vault is the single place for concepts (§7).

Each project is **self-contained**: own `pyproject.toml`, own `uv.lock`, own README; extractable to a standalone repo.

## 4. Git workflow and traceability

**Branches**
| Branch | Role | Receives | Protection |
|---|---|---|---|
| `main` | Released, portfolio-facing history | PRs from `dev` only (release PRs) | No direct push, PR required, no force-push, no deletion, applies to admins |
| `dev` | Stable integration | PRs from work branches | Same as `main` |
| `<type>/<issue#>-<slug>` | Work | Commits | None; deleted after merge |

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `infra`. Example: `feat/12-ais-ingestion`.

**Traceability chain**
1. **Issue** (template: feature / bug / learning) states the what and why; labelled by type and project.
2. **Branch** is cut from `dev` and carries the issue number.
3. **Commits** follow Conventional Commits with the project as scope: `feat(marineflow): add AIS parser`. Environment-level changes use scope `lab`.
4. **PR** into `dev` uses the template (summary, `Closes #n`, how it was tested, *Why / what I learned*). **Squash merge** → one clean commit per change on `dev`.
5. **Release**: PR `dev → main` titled `release: vX.Y.Z`, **merge commit** (preserves the squashed history), tag `vX.Y.Z` on `main`, CHANGELOG updated. SemVer at repo level.

Required approvals: 0 (a two-member team where one member is an agent cannot self-approve); required status checks are added once CI exists.

**Bootstrap exception:** the very first commits (spec, plan, foundation) go to `main` before protection exists; `dev` is created from that commit, then both are protected. From then on, the rules apply to Claude too.

## 5. Claude — identity and operating manual (`CLAUDE.md`)

1. **Identity** — senior data engineer and teammate; the brain of the operation, not a code generator.
2. **Character** — direct, opinionated, *disagree and commit*; pragmatic (YAGNI, cost-aware); creative in proposals; conservative with risk (destructive, cost-incurring or public actions always confirmed).
3. **Language rules** — as in §1.
4. **Repo map + Git workflow** — summary of §3 and §4.
5. **Mentor protocol** — after meaningful work, close with a short *Why* block (decision → alternatives → underlying concept). Durable decisions → ADR. New concepts → vault note.
6. **Conventions** — Python via uv, ruff, pytest; SQL lowercase with CTEs; Terraform per cloud inside each project (`projects/<p>/infra/<cloud>/`).
7. **Security & cost** — never commit secrets (only `.env.example`); gitleaks pre-commit; cloud labs use free tier first, budget alerts, and a documented `make destroy`.
8. **Efficiency** — targeted reads over broad ones; no custom agents until a task repeats or needs isolation; graphify when it saves tokens (§6).
9. **Evolution loop** — see §6.
10. **Definition of Done** — tests green, project README with architecture diagram, run instructions, "What I learned" linking vault notes, issue closed via PR.

## 6. Long-term memory architecture

Three tiers; what is always loaded stays small, what grows is read on demand.

| Tier | Store | Loaded | Health rule |
|---|---|---|---|
| Hot | Claude's file memory (`~/.claude/projects/.../memory/`) | Index every session | `MEMORY.md` ≤ ~40 lines; consolidated at each retro (merge, prune stale) |
| Warm | This repo: `CLAUDE.md`, ADRs, specs, git history | When working on it | One decision, one ADR |
| Deep | Obsidian vault | On demand (grep, wikilinks) | Notes carry `status: seed → growing → evergreen`; merge rather than duplicate |

**graphify** is a derived index layer over the repo and the vault — never the source of truth. Claude has discretion to build/update it (`--update`, incremental) whenever it saves tokens without losing context; expected trigger: first project with real code, or ~100 vault notes.

**Evolution loop**
1. During work: store preferences, corrections and confirmed approaches in memory.
2. End of each project: 5-minute retro (Claude, Tomas, process) → concrete edits to `CLAUDE.md` and memory consolidation.
3. Proactive requests: Claude asks for skills/plugins/MCPs/permissions when a real gap appears, with cost/benefit.

**Custom agents/skills:** only `/new-project` now (creates issue + branch from `dev`, copies `_template`, registers the project in the README index). Candidates deferred until needed: `data-reviewer` agent, a docs MCP (e.g. Context7).

## 7. Second brain (Obsidian)

- **Source:** existing vault `~/Downloads/Obsidian_Data_Engineering_Second_Brain` (30 notes, numbered areas, templates, EN).
- **Move to:** `~/Data Engineering/Second Brain/` (Downloads is not a durable location). Tomas re-opens it in Obsidian from the new path.
- **Versioning:** its own private repo `TomasRipsky/second-brain`; `.gitignore` excludes `.obsidian/workspace*.json` and caches.
- **Access:** added to `permissions.additionalDirectories` in `.claude/settings.json`.
- **Flow:** new concepts met in projects are created/enriched with the vault's Concept Template; project READMEs link vault notes; `07 - Laboratory` notes link back to projects.
- No Obsidian plugins required now.

## 8. Tooling

Installed via Homebrew: `uv`, `ruff`, `pre-commit`, `gitleaks`, `duckdb`.
Deferred: Java/Spark, dbt, AWS CLI, Azure CLI, Node.
Git: default branch `main`; `gh` uses HTTPS with its credential helper (done).

## 9. Out of scope

- CI workflows (added with the first project that has real tests; then made a required status check).
- `shared/` library, root docker-compose stack, per-cloud infra.
- Importing existing repos (`marineflow`, `citypulse_analytics`) — separate decision later.
- Building a graphify graph now.

## 10. Verification

- `pre-commit run --all-files` passes.
- A planted fake secret in a scratch file is blocked by gitleaks (then removed).
- `cd projects/_template && uv run pytest && uv run ruff check .` passes.
- `gh repo view TomasRipsky/data-engineering-lab` shows `main` and `dev`; `gh api` confirms protection on both; a direct `git push origin dev` is rejected.
- Vault opens from the new path, its git history exists, `TomasRipsky/second-brain` is private.
