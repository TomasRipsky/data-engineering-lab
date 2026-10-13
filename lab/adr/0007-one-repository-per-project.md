# 0007 — One repository per project; the lab is the base

- **Status:** Accepted
- **Date:** 2026-10-13
- **Supersedes:** [0001](0001-monorepo-with-self-contained-projects.md), [0005](0005-one-lab-site-with-a-shared-design.md). **Amends:** [0006](0006-world-and-countries-structure.md).

## Context
ADR 0001 put every project in one repository so that conventions and Claude's context would not
drift, and required each project to stay self-contained "so it can be extracted to a standalone
repo without untangling anything". After one project the costs of the monorepo were visible and
growing with every project to come:

- The repository grows without bound: one history, one issue tracker, one release line and one
  changelog for unrelated products.
- GitHub gives a repository one Pages site, one set of environments and one default branch, so
  projects shared them: one project's pipeline deployed the whole site (ADR 0005), cloud trust was
  scoped by workflow-name prefix inside a shared repository, and CI needed path filters — which is
  why a PR could merge with no checks at all (issue #53).
- A portfolio reader looks for a repository per product. CityPulse and MarineFlow already live
  that way, with their own sites.

The thing ADR 0001 was protecting — one place for the rules and the agent — does not need the
projects' code to sit next to it.

## Decision
**Each project is its own repository**: code, infrastructure, docs (`README.md`, `docs/guide.md`,
`docs/decisions/`, `docs/design/`), its public site and its CI/CD, its own issues, releases and
changelog. Clones live next to the lab in `~/Data Engineering/Proyectos Data/<name>`.

**The lab is the base every project starts from** and the only home of what is shared:

- the rules (`CLAUDE.md`, `lab/conventions.md`, `lab/security-and-cost.md`, lab ADRs, tech radar);
- the agent (`agent/`, `.claude/` skills, hooks, reviewer, settings) and Claude's memory;
- `template/` — what a new repository starts as, including the shared site look;
- the portfolio hub (`site/`): one static page linking every project's own site.

Claude Code sessions start **in the lab** and add the project's clone as a working directory, so
there is exactly one copy of the rules, skills and memory. Project repositories carry only a short
`CLAUDE.md` that points here. Skills act on a named target repository.

Shared code is still extracted only when two projects duplicate it — then as a package of its
own, not as a folder here.

## Alternatives considered
- **Stay a monorepo** — keeps atomic cross-project changes, which we never needed; keeps every
  cost above.
- **Self-contained project repositories** (each with its own copy of `.claude/` and the rules) —
  sessions could start anywhere, but N copies drift, every lesson must be ported by hand and
  Claude's memory splits per directory. This is the drift ADR 0001 feared.
- **Git submodules or a GitHub template repository** — submodules add a second versioning problem
  for a solo team; a template repository cannot be updated together with the skills that use it.
  A `template/` folder copied by the `new-project` skill is the smallest thing that works.
- **Keep one shared site fed by every project** (ADR 0005's `lab-site` plan) — couples every
  project's release to one build and one design; projects wanted their own personality anyway.

## Consequences
- pitwall was extracted on 2026-10-13 with its history (`git filter-repo`); the lab's own history
  and tags v0.1.0–v1.0.0 still contain it. Spec and plan: `lab/design/specs/2026-10-13-repo-per-project-design.md`.
- A project's CI runs on every pull request (no path filters), its cloud trust names its own
  repository, and a release of the lab no longer touches any production system.
- The shared look is **copied** at bootstrap (`template/site/`) and then belongs to the project:
  consistency is a starting point, not an enforced dependency.
- Old dashboard URLs under `/data-engineering-lab/pitwall/` are kept alive by redirect stubs in
  `site/pitwall/`.
- Per-repository chores multiply (settings, rulesets, labels, environments, Dependabot):
  `new-project` automates the common ones.
- Lessons learned inside a project land in the lab (`agent/lessons.md`, `template/`) through a
  lab PR — a second PR, accepted as the price of one source of truth.
- The secret-file deny rules in `.claude/settings.json` are anchored at the lab root, so they are
  repeated for `~/Data Engineering/Proyectos Data/**`.
- The world-and-countries picture of ADR 0006 holds with one change: the countries are
  repositories, not folders; `projects/` is gone and `site/` is the hub.
