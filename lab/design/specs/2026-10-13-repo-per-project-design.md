# One repository per project — design

- **Date:** 2026-10-13
- **Issue:** data-engineering-lab#60
- **Supersedes:** lab ADR 0001 (monorepo), lab ADR 0005 (one lab site). Amends lab ADR 0006.

## 1. Intent

Tomas (2026-10-13): the monorepo will grow without bound, so every project moves to its own
repository — code, infrastructure, docs, site and CI together — and the lab stays as the base:
the knowledge, the rules, the agent and the template every new project starts from. pitwall is
the first extraction and must work exactly as before: CI on pull requests, the Monday production
pipeline, the public dashboard.

Decisions Tomas took on 2026-10-13:

| Question | Decision |
|---|---|
| Where the agent's machinery lives | **Lab as the single base.** Sessions start in the lab; project repos are sibling clones. One copy of rules, skills, hooks and memory. |
| The lab site and its public URL | **Minimal static hub + redirects.** The dashboard moves to the project's own Pages site; the lab keeps one portfolio page and redirect stubs for the old URLs. |
| History | **Preserved.** The new repository carries pitwall's commits. |
| Authority | **Full cutover in one go**, including prod, Pages, the schedule and the releases into `main` of both repositories. Stop only on failure. |

Assumptions (stated to Tomas, not objected): repository `TomasRipsky/pitwall`, public, cloned at
`~/Data Engineering/Proyectos Data/pitwall` next to CityPulse and MarineFlow; the lab's own
history is not rewritten; open pitwall issues move with the project.

## 2. Verified facts (2026-10-13)

- `TomasRipsky/pitwall` does not exist — source: `gh repo view TomasRipsky/pitwall` → "Could not resolve to a Repository".
- The lab is public, default branch `dev`, squash + merge commits allowed, `delete_branch_on_merge` on, repository ID `1396373223` — source: `gh api repos/TomasRipsky/data-engineering-lab`.
- `dev` and `main` are protected by rulesets `protect-dev` (PR required, squash only, no deletion, no force push) and `protect-main` (same, merge commits only) — source: `gh api …/rulesets/{id}`.
- Environments: `dev` (no rules), `prod` and `github-pages` (branch policy `dev`, `main`). Variables: `PITWALL_PROJECT`, `PITWALL_WIF_PROVIDER`, `PITWALL_SERVICE_ACCOUNT` per environment, `PITWALL_DASHBOARD_SERVICE_ACCOUNT` in prod, repository variable `PITWALL_SCHEDULE=on`. No secrets — source: `gh variable list`, `gh secret list`, `gh api …/environments`.
- Pages is built by a workflow (`build_type: workflow`) — source: `gh api …/pages`.
- Workload Identity Federation accepts only tokens whose `repository_id` is the lab's and whose `workflow_ref` starts with `TomasRipsky/data-engineering-lab/.github/workflows/pitwall-`; prod also requires `environment == 'prod'` and `ref` in `dev`/`main`. Both values are Terraform variable defaults — source: `infra/gcp/iam.tf`, `variables.tf`.
- Terraform state is local, one workspace per environment (`infra/gcp/terraform.tfstate.d/{dev,prod}`), git-ignored — source: `ls`, `git check-ignore`.
- Local tooling: Terraform 1.16.1, gcloud 584.0.0 with valid application-default credentials, `gh` token with `repo` and `workflow` scopes, `git-filter-repo` runnable with `uvx` — source: the commands' output.
- `gh issue transfer <n> <repo>` exists — source: `gh issue transfer --help`.
- Sibling projects already live in their own repositories with their own Pages sites: `CityPulse_Analytics` (https://tomasripsky.github.io/CityPulse_Analytics/), `marineflow` (https://tomasripsky.github.io/marineflow/) — source: `gh api …/pages`.
- The branch `docs/43-pitwall-guide` holds unmerged work on both sides: the pitwall guide and three `chore(agent)` changes (`CLAUDE.md`, `agent/`, the template's `docs/guide.md`) — source: `git diff --stat origin/dev...docs/43-pitwall-guide`.

**Assumption:** changing the provider's `attribute_condition` and the two `workloadIdentityUser`
members is an in-place update / replace of IAM bindings only, never a replacement of the pool,
the service accounts, the bucket or the datasets. Risk if wrong: `terraform apply` would destroy
data-bearing resources. Check: read `terraform plan` for dev before applying anything; abort on
any `destroy` or `replace` outside the provider and the two WIF members.

## 3. Target state

### 3.1 The pitwall repository

`TomasRipsky/pitwall`, public, default branch `dev`, branches `dev` and `main` with the lab's
rulesets, squash merges into `dev`, merge commits into `main`.

```
README.md  CHANGELOG.md  CLAUDE.md  Makefile  pyproject.toml  uv.lock  .env.example
src/pitwall/   tests/   transform/   infra/gcp/
docs/          guide.md, decisions/, design/{specs,plans}
site/          package.json, observablehq.config.js, src/ (pages at the site root)
.github/       workflows/pitwall-ci.yml, pitwall-pipeline.yml, dependabot.yml, templates
.pre-commit-config.yaml  .editorconfig  .gitignore
```

- **History.** `git filter-repo` over a fresh clone keeps `projects/pitwall/` (moved to the root),
  `site/`, the two `pitwall-*` workflows and the pitwall specs and plans that once lived under
  `docs/superpowers/` (renamed to `docs/design/` so each file has one continuous history).
  Branches kept: `dev`, `main`, `docs/43-pitwall-guide`. Lab tags are not carried.
- **Issue references.** Commit messages say `#49` meaning the lab's issue 49. In the new
  repository that would autolink to an unrelated number, so every `#N` becomes
  `data-engineering-lab#N` — readable, and deliberately *not* GitHub's `owner/repo#N` form:
  pushing 60 commits containing `Closes owner/repo#N` would write cross-reference events on every
  lab issue and could close an open one.
- **Adaptation** is an ordinary, reviewable PR on top of the extracted history, not part of the
  rewrite: pages move from `site/src/pitwall/` to `site/src/` (base path `/pitwall/`), the lab
  landing page is dropped, workflows lose `working-directory: projects/pitwall` and their path
  filters, `make site-data` writes to `site/src/data`, Terraform's repository variables point at
  the new repository, root hygiene files are added, and docs stop saying `projects/pitwall/`.
- **Workflow names stay `pitwall-ci.yml` and `pitwall-pipeline.yml`.** The WIF condition keys on
  the `pitwall-` prefix; keeping it means the only IAM change is the repository.
- **CI without path filters.** The whole repository is the project, so every PR runs CI. That
  removes the caveat behind data-engineering-lab#53 (a path-filtered PR reports no checks) for
  this repository.
- **Versioning.** The repository starts at `v1.0.0` ("standalone repository"); its `CHANGELOG.md`
  opens with the pitwall entries of the lab's releases 0.3.0–1.0.0 as history.
- **Agent pointer.** A short `CLAUDE.md` says the rules, skills and agent live in the lab and
  sessions start there.

### 3.2 The lab

```
README.md  CLAUDE.md  CHANGELOG.md
agent/     how Claude works and evolves
lab/       conventions, security-and-cost, tech radar, ADRs, designs
template/  what a new project repository starts as (was projects/_template)
site/      static portfolio hub + redirect stubs (no build)
.claude/   skills, agents, hooks, settings
.github/   workflows/lab-site.yml, templates
```

- `projects/pitwall/`, both `pitwall-*` workflows and the Observable site are removed. History and
  the tags v0.1.0–v1.0.0 are untouched.
- **`template/`** grows into a complete standalone repository: the Python project it already is,
  plus `.gitignore`, `.pre-commit-config.yaml`, `.editorconfig`, issue and PR templates,
  `dependabot.yml`, a `ci.yml` (lint + test), a `CLAUDE.md` pointer, `CHANGELOG.md`, and a `site/`
  skeleton that carries the shared look (`lab.css`, `lab.js`) and the page conventions that lived
  in `site/README.md`. The shared design is copied at bootstrap and then belongs to the project.
- **`site/`** becomes plain HTML: `index.html` (one card per project: pitwall, CityPulse,
  MarineFlow) and one redirect stub per old dashboard URL (`pitwall/index.html`,
  `race-strategy.html`, `tyre-wear.html`, `undercut.html`, `about.html`) using
  `<meta http-equiv="refresh">` plus a canonical link, so old links work without JavaScript.
  `lab-site.yml` uploads the folder to Pages on pushes to `main`. No npm in the lab.
- **Skills and hooks become repo-aware.** The Bash tool's working directory resets when it leaves
  the session's folders, so every block names its repository explicitly.
  - `new-project`: copies `template/` to `~/Data Engineering/Proyectos Data/<name>`, initialises
    git with `main` and `dev`, creates the public repository (after Tomas's OK — it is public),
    applies settings, rulesets and labels, then registers the project in the lab README (a lab PR)
    and the vault.
  - `ship`, `release`: run from the target repository's root; lab-only steps (agent changelog,
    hook tests) are marked as such; the release skill states what a push to `main` triggers in a
    project repository.
  - `pr-reviewer`: is given the repository path; reads the rules from the lab and the decisions
    from the project.
  - `world-status`: lab branch, issues and PRs as today, then one line per project repository
    listed in the README's Projects table (open issues and PRs by the owner, last workflow run).
- **Secret deny rules** in `.claude/settings.json` are anchored at the lab root, so they stop
  covering project files once projects live elsewhere. The same patterns are added for
  `~/Data Engineering/Proyectos Data/**`.
- **Docs.** New lab ADR 0007; ADRs 0001 and 0005 marked superseded, 0006 amended. `README.md`
  (map, Projects table with repository links), `CLAUDE.md`, `lab/conventions.md`,
  `lab/security-and-cost.md`, `agent/README.md`, changelogs and lessons updated. Lab release
  `v2.0.0` (structural change).

### 3.3 Cloud and GitHub wiring

- GCP projects `pitwall-tr-dev` and `pitwall-tr-prod` are unchanged. Cost stays €0/month; no
  resource is created.
- Terraform: `github_repository` → `TomasRipsky/pitwall`, `github_repository_id` → the new
  repository's ID. One `terraform apply` per environment rebinds WIF. The local state directories
  and `.terraform/` are **moved** to the new clone before any apply.
- The new repository gets environments `dev` and `prod` (prod limited to `dev` and `main`), the
  variables via `make gh-vars`, Pages with `build_type: workflow`, and `PITWALL_SCHEDULE=on` only
  after a green production run.
- The lab loses `PITWALL_SCHEDULE`, both environments and their variables once production runs
  from the new repository.

## 4. Cutover order

Each step leaves the system working or is the single step that switches it; the dashboard never
goes dark because the old Pages site stays published until the lab hub replaces it.

1. **Extract** — filter a fresh clone, compare its tree with the lab's files, create the
   repository with Actions disabled (the first push to `main` must not start a pipeline), push,
   apply settings, rulesets, labels and environments, enable Actions, move the local-only files
   (`.env`, `.lake/`, Terraform state).
2. **Adapt on dev** — the adaptation PR; `terraform apply` on **dev**; `make gh-vars ENV=dev`. From
   here the lab's dev CI can no longer authenticate — intended. The PR's own CI (lint, tests,
   Terraform validate, dbt in per-PR datasets, site data, site build) is the proof that dev works.
   `pr-reviewer`, then squash merge.
3. **Production** — turn the lab's schedule off; `terraform apply` on **prod**;
   `make gh-vars ENV=prod`; enable Pages; release PR `dev → main` (merge commit). The push to
   `main` runs the pipeline on prod (reload, dbt build and tests, export, site build, deploy).
   Verify the run and the live site at `https://tomasripsky.github.io/pitwall/`. Then
   `PITWALL_SCHEDULE=on`, tag and release `v1.0.0`.
4. **Lab** — the restructure PR into `dev` (includes the agent changes from
   `docs/43-pitwall-guide`), `pr-reviewer`, merge; transfer the open pitwall issues; release
   `v2.0.0` into `main`, which deploys the hub and the redirects; verify the old dashboard URL
   lands on the new site; delete the lab's stale environments, variables and the lab copy of the
   guide branch.
5. **Persist** — memory, vault notes, tutor review, and the guide branch in the new repository
   rebased onto the adapted layout.

**Rollback.** Until step 3 the lab is untouched and production still runs from it; undoing step 2
is `terraform apply` on dev with the old variable values. After step 3, rollback is the same two
variables on prod plus `PITWALL_SCHEDULE=on` in the lab — possible until step 4 merges.

## 5. Risks

| Risk | Guard |
|---|---|
| The Terraform plan touches more than IAM | Read the dev plan first; abort on any destroy/replace outside the WIF provider and members. |
| Local Terraform state lost in the move | Move (same disk, atomic), then `terraform plan` from the new clone must show only the intended change. |
| The first push to `main` triggers the production pipeline in an unconfigured repository | Actions disabled until settings and environments exist. |
| Commit messages cross-link or close lab issues | `#N` rewritten to the non-linking `data-engineering-lab#N`. |
| Files lost or altered by the history rewrite | `diff -r` between the filtered `dev` tip and the lab's `projects/pitwall`, `site` and workflows: no differences allowed. |
| The Monday schedule fires mid-cutover | Today is Tuesday; the lab's schedule is turned off before prod is rebound. |
| The public dashboard URL breaks | Redirect stubs for all five old URLs, deployed after the new site is live. |
| Secrets in project folders readable by Claude | Deny rules extended to `Proyectos Data/**`; verified against the current Claude Code permission syntax. |
| A rule silently lost while editing `CLAUDE.md` and the skills | Each edited file is diffed against its previous version; removed lines must be about the monorepo layout. |

## 6. Out of scope

- Moving CityPulse or MarineFlow, or changing their repositories.
- Required status checks (data-engineering-lab#53) — easier now, still a separate change.
- Finishing the pitwall tutoring and guide — the branch moves, the work continues there.
- A shared package or a GitHub template repository: the lab's `template/` folder is the template.
