# One repository per project — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract pitwall into `TomasRipsky/pitwall` with its history and a working CI, production pipeline and public site, and turn the lab into the base every project repository starts from.

**Architecture:** `git filter-repo` produces the new repository from a fresh clone; an ordinary PR adapts it to stand alone; Workload Identity Federation is rebound per environment with one Terraform variable change; the lab then drops the project, swaps its Observable site for a static hub with redirects, and makes its skills and hooks repo-aware.

**Tech Stack:** git + git-filter-repo, GitHub CLI and REST API (rulesets, environments, Pages), Terraform (GCP IAM/WIF), GitHub Actions, Observable Framework, Claude Code skills/hooks/settings.

**Spec:** `lab/design/specs/2026-10-13-repo-per-project-design.md`

**Execution:** native, in one session — the tasks are an ordered cutover against live cloud and GitHub state, not independent units. Tomas authorised the full cutover on 2026-10-13 (spec §1).

## Global Constraints

- Paths: lab `LAB=~/Data Engineering/Claude Code Enviroment`; project clone `PW=~/Data Engineering/Proyectos Data/pitwall`. Every shell block starts with an explicit `cd` (the Bash tool resets its directory outside the session's folders).
- Never read or print `.env`, `*.tfstate` or `profiles.yml`: they are moved with `mv`, never opened.
- Lab changes: branch `refactor/60-repo-per-project`, PR into `dev` with `Closes #60`, through `ship`.
- pitwall changes: issue → `<type>/<n>-<slug>` from `dev` → PR into `dev` → squash; release `dev → main` with a merge commit.
- Commits: Conventional Commits; in the lab scope `lab`/`agent`; in pitwall the scope is the component (`site`, `ci`, `infra`, `docs`) or none.
- Workflow file names stay `pitwall-ci.yml` and `pitwall-pipeline.yml` (WIF condition prefix).
- No new action, package or provider versions: every pin is carried over unchanged.
- Cost: €0; no cloud resource is created or destroyed. Abort any `terraform apply` whose plan destroys or replaces anything other than the WIF provider's condition and the `workloadIdentityUser` members.
- Historical specs and plans are records: their text is not rewritten, in either repository.
- All repository and vault content in English.

## Review Focus

1. **A file lost or changed by the history rewrite** → Task 1 `diff -r` of the filtered `dev` tip against the lab's files; zero differences.
2. **Terraform touching data-bearing resources** → Task 3 and Task 4 read the plan summary before applying; only IAM changes allowed.
3. **Old repository still able to mint GCP tokens / new one unable** → Task 3: the new repository's CI `dbt` and `site-data` jobs pass (they authenticate); after Task 4 the provider's condition holds the new repository ID only.
4. **Site links broken by flattening and the new base path** → Task 2 builds the site locally and greps `dist/` for `/data-engineering-lab/` and `pitwall/pitwall`; Task 4 loads all five live pages.
5. **Old public URLs dead** → Task 6 requests the five old URLs after the hub deploys; each must contain the new location.
6. **A rule dropped from `CLAUDE.md` or a skill** → Task 5 reviews `git diff dev -- CLAUDE.md .claude lab/conventions.md`; every removed line must concern the monorepo layout.
7. **Secrets in project folders readable** → Task 5 verifies the permission-rule path syntax against the current Claude Code docs before writing the rules.
8. **A project bootstrapped from a broken template** → Task 5 copies `template/` to a scratch directory exactly like `new-project` and runs `uv sync`, `make lint`, `make test` there.

## Execution — tutoring protocol

Brief before each block, execute without blocking, tutor review after. Vault notes: polyrepo vs monorepo, extracting history with git-filter-repo, WIF trust bound to a repository, redirects on a static host.

- **Block 1 — A new country:** Tasks 1, 2
- **Block 2 — Moving the keys:** Tasks 3, 4
- **Block 3 — The lab as base:** Tasks 5, 6
- **Block 4 — Close:** Task 7

---

### Task 1: Extract the history and create the repository

- [ ] Fresh clone of the lab into the scratchpad (`git clone --no-local`), keeping only `dev`, `main`, `docs/43-pitwall-guide`; delete every tag.
- [ ] `uvx git-filter-repo` with paths `projects/pitwall/`, `site/`, `.github/workflows/pitwall-ci.yml`, `.github/workflows/pitwall-pipeline.yml`, glob `docs/superpowers/*/*pitwall*`; renames `projects/pitwall/` → root and `docs/superpowers/` → `docs/design/`; message callback `#N` → `data-engineering-lab#N` (regex `(?<![\w/])#(\d+)`).
- [ ] **Check:** `diff -r` filtered `dev` vs lab `dev` for `projects/pitwall` ↔ root (tracked files only), `site`, both workflows → no output. `git log --oneline | wc -l` per branch recorded; `git log --grep '(^|[^-/\w])#[0-9]+' -E` → empty.
- [ ] `gh repo create TomasRipsky/pitwall --public` (description, topics, homepage `https://tomasripsky.github.io/pitwall/`); disable Actions (`PUT actions/permissions enabled=false`); push the three branches; default branch `dev`; `allow_rebase_merge=false`, `delete_branch_on_merge=true`, wiki off; rulesets `protect-dev` and `protect-main` copied from the lab's JSON; `gh label clone` (then drop `project:*`); environments `dev`, `prod` (custom branch policy `dev`, `main`); enable Actions.
- [ ] Move the filtered clone to `PW`; `mv` from the lab's `projects/pitwall`: `.env`, `.lake`, `infra/gcp/terraform.tfstate.d`, `infra/gcp/.terraform`. `pre-commit install` comes with Task 2 (the config arrives there).
- [ ] **Check:** `gh repo view TomasRipsky/pitwall --json defaultBranchRef,visibility`; `gh run list -R TomasRipsky/pitwall` → no runs.

### Task 2: Adapt pitwall to stand alone (PR into pitwall `dev`)

- [ ] Issue "refactor: stand alone as its own repository", branch `refactor/<n>-standalone`.
- [ ] **Site:** `git mv site/src/pitwall/* site/src/`; remove the lab landing `site/src/index.md` first and `site/src/style.css` if nothing imports it; fix imports (`../components/lab.js` → `./components/lab.js`, CSS import likewise, fonts path), `observablehq.config.js` (`title`, `base: "/pitwall/"`, flat `pages`, footer linking to this repository and to the lab), `site/README.md` rewritten for one project.
- [ ] **Code:** `Makefile` `SITE_DIR := site`, `site-data` → `--out site/src/data`; docstring in `src/pitwall/site_data.py` and the CLI help; any test asserting the old path.
- [ ] **Workflows:** drop `defaults.run.working-directory` / per-step `projects/pitwall` prefixes and both `paths:` filters; artifact paths `site/src/data`; `cache-dependency-path: site/package-lock.json` stays.
- [ ] **Infra:** `variables.tf` defaults → `TomasRipsky/pitwall` and the new repository ID.
- [ ] **Root files:** `.gitignore` (lab root rules + the project's), `.pre-commit-config.yaml`, `.editorconfig`, `.github/dependabot.yml` (actions weekly, npm `/site` monthly, plus `uv` and `terraform` only if the lab had them — it did not), issue and PR templates, `CLAUDE.md` pointer, `CHANGELOG.md` (history from lab 0.3.0–1.0.0, `[Unreleased]` with this change).
- [ ] **Docs:** `README.md` and `docs/guide.md` paths (`projects/pitwall/` → root, lab ADR links absolute), new dashboard URL; ADRs get a one-line note where they name the lab site; specs and plans untouched.
- [ ] **Check:** `pre-commit install`; `uv sync --locked`, `make lint`, `make test`; `terraform -chdir=infra/gcp fmt -check && validate`; `make site ENV=dev` then `grep -rl "data-engineering-lab/\|pitwall/pitwall" site/dist` → empty; open `site/dist` locally and load the five pages.
- [ ] `grep -rn "projects/pitwall\|\.\./\.\./site" --exclude-dir={.git,.venv,node_modules,dist,design}` → empty.

### Task 3: Rebind dev and land the adaptation

- [ ] `cd PW && make plan ENV=dev` → only the provider (update in place) and the pipeline `workloadIdentityUser` member (replace) change; then `make apply ENV=dev`, `make gh-vars ENV=dev`.
- [ ] Push, open the PR (`Closes #<n>`). **Check:** all six jobs green — `python`, `terraform`, `dbt`, `site-data`, `site-build` (the dbt and site-data jobs prove WIF).
- [ ] `pr-reviewer` on the branch (focus: Review Focus 3, 4 and workflow path changes); fix Critical/Important; squash merge; issue closed.
- [ ] Manual run `pitwall-pipeline` with `env=dev`, `mode=none` → `run` job green (site jobs skip outside prod).

### Task 4: Production cutover and first release

- [ ] `gh variable delete PITWALL_SCHEDULE -R TomasRipsky/data-engineering-lab`.
- [ ] `make plan ENV=prod` (same IAM-only shape, two members) → `make apply ENV=prod` → `make gh-vars ENV=prod`.
- [ ] Enable Pages: `gh api -X POST repos/TomasRipsky/pitwall/pages -f build_type=workflow`; `github-pages` environment branch policy `dev`, `main`.
- [ ] Release: changelog PR into `dev` (`[1.0.0] - 2026-10-13`), then PR `dev → main` titled `release: v1.0.0`, merge commit.
- [ ] **Check:** the `pitwall-pipeline` run on `main` is green end to end (run, site-data, site-build, deploy); `https://tomasripsky.github.io/pitwall/` and its four subpages render with data (browser); the old lab site still serves.
- [ ] `gh variable set PITWALL_SCHEDULE --body on -R TomasRipsky/pitwall`; `gh release create v1.0.0 --target main`.
- [ ] Transfer lab issues #43 and #50; rename the guide branch to `docs/<new#>-guide`, merge `dev` into it, fix `projects/pitwall/` paths in the guide, push.

### Task 5: Restructure the lab (PR into lab `dev`)

- [ ] Merge `origin/docs/43-pitwall-guide` into the branch (brings the agent changes; pitwall files go in the next step).
- [ ] `git rm -r projects/pitwall .github/workflows/pitwall-*.yml site`; `git mv projects/_template template`.
- [ ] **Template:** add `.gitignore`, `.pre-commit-config.yaml`, `.editorconfig`, `.github/{ISSUE_TEMPLATE,pull_request_template.md,dependabot.yml,workflows/ci.yml}`, `CLAUDE.md`, `CHANGELOG.md`, `site/` skeleton (`package.json`, lockfile, `observablehq.config.js`, `src/index.md`, `src/components/lab.{css,js}`, `README.md` with the page conventions). README says how the template is used.
- [ ] **Hub:** `site/index.html` (cards: pitwall, CityPulse, MarineFlow; light and dark; no external requests), five redirect stubs under `site/pitwall/`, `.github/workflows/lab-site.yml` (push to `main` on `site/**` + manual; upload-pages-artifact and deploy-pages at the pinned SHAs).
- [ ] **Skills/agent/hooks:** `new-project` rewritten (spec §3.2); `ship` and `release` take a target repository; `pr-reviewer` reads rules from the lab and code from the given path; `world-status.sh` adds a line per project repository parsed from the README table, its test updated first (new expectation: `pitwall:` line with issues and last run; strangers' titles still hidden; hang still under 10 s per the existing budget — raise the hook timeout to 30).
- [ ] **Settings:** deny rules for `Proyectos Data/**` after checking the path syntax in the current Claude Code permissions docs.
- [ ] **Docs:** ADR `0007-one-repository-per-project.md`; status lines of 0001, 0005, 0006; `README.md`, `CLAUDE.md`, `lab/conventions.md`, `lab/security-and-cost.md`, `agent/README.md`, `agent/lessons.md`, `agent/CHANGELOG.md`, `CHANGELOG.md`, root `.gitignore`, `dependabot.yml`, `ruff.toml`.
- [ ] **Check:** hook tests pass; template bootstrap in a scratch dir (`uv sync`, `make lint`, `make test`) passes; relative-link check over all tracked Markdown outside `lab/design/` → no dead links; `git grep -n "projects/pitwall\|projects/_template\|projects/<p>" -- ':!lab/design' ':!agent/retros' ':!CHANGELOG.md' ':!agent/CHANGELOG.md' ':!lab/adr/000[1-6]*'` → empty; `git diff dev -- CLAUDE.md` reviewed line by line.
- [ ] `ship`: PR `Closes #60`, `pr-reviewer`, squash merge.

### Task 6: Lab release and clean-up

- [ ] Changelog PR (`[2.0.0] - 2026-10-13`), PR `dev → main`, merge commit, `gh release create v2.0.0`.
- [ ] **Check:** `lab-site` run green; `curl -s` the hub and the five old dashboard URLs → each stub contains `https://tomasripsky.github.io/pitwall/`.
- [ ] Delete lab environments `dev` and `prod` (their variables go with them); delete the lab's remote and local `docs/43-pitwall-guide` after confirming `git diff dev origin/docs/43-pitwall-guide -- . ':!projects/pitwall'` shows nothing the lab lacks; remove the leftover untracked `projects/` directory (caches only — list it first).

### Task 7: Persist

- [ ] Memory: `lab-state`, `feedback-consistent-visuals`, new `project-repo-per-project`; index updated.
- [ ] Vault: pitwall project note (new repository and paths); notes per the tutoring list above, enriched before created.
- [ ] Final report: what changed, evidence, what the next conversation starts with.
