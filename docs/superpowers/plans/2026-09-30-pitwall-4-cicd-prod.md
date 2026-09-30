# pitwall — Plan 4: CI/CD and production

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every PR touching pitwall is linted, tested, Terraform-validated and dbt-built in throwaway BigQuery datasets; a GitHub Actions pipeline ingests → loads → transforms on demand (dev/prod) and every Monday (prod); prod exists and holds 2023 → current season, all through Workload Identity Federation with no keys.

**Architecture:** Two workflows, `pitwall-ci.yml` (PRs) and `pitwall-pipeline.yml` (schedule + manual), reuse the Makefile targets so local and CI runs are the same commands. GitHub Environments `dev` and `prod` hold each environment's project, WIF provider and service account as variables, published from Terraform outputs by `make gh-vars`. Prod runs code from `main` only, so a release (v0.3.0) precedes the prod backfill.

**Tech Stack:** GitHub Actions (checkout v7, google-github-actions/auth v3 + setup-gcloud v3, astral-sh/setup-uv v10, hashicorp/setup-terraform v4), Terraform, dbt, bq CLI.

**Spec:** `docs/superpowers/specs/2026-09-29-pitwall-design.md` (§7 orchestration & CI/CD, §9 infrastructure). Roadmap change: the old "Plan 4 — CI/CD + dashboard" is split; the Evidence dashboard on GitHub Pages becomes **Plan 5**.

## Global Constraints

- No service-account keys anywhere; GitHub → GCP only via WIF (`id-token: write` only on jobs that need GCP).
- Workflow files must be named `pitwall-*.yml` (the WIF attribute condition requires it).
- Prod jobs run in GitHub Environment `prod`, check out `main`, and may only start from `dev` or `main` (deployment branch policy + WIF condition).
- CI never touches prod. CI datasets are `ci_pr_<n>_{staging,intermediate,marts,audit}` in dev, created with a 1-day default table expiration and dropped in an `if: always()` step.
- Forks cannot mint OIDC tokens: their PRs run lint/tests/terraform, and the dbt job is skipped (not failed).
- The pitwall CI is **not** a required status check on `dev`: path-filtered workflows never report on unrelated PRs, and a required check would block them.
- Hard stops for Tomas: (1) creating the prod project (cost), (2) cutting release v0.3.0 to `main`.
- GitHub cron workflows in public repos are disabled after 60 days without repo activity (documented in README; no keep-alive).

## Review Focus

1. **A PR from a fork** → the dbt job is skipped cleanly, lint/tests still run; verified by the job's `if:` in Task 3 and its dry-run reading.
2. **A dbt test failing in CI** → the per-PR datasets are still dropped (`if: always()`), and the 1-day expiration catches anything left; verified in Task 5 by listing datasets after the CI run.
3. **`workflow_dispatch` with `mode=season` and an empty or non-numeric value** → fails in the first step with a clear message before touching GCP; tested in Task 6.
4. **The 2023 season has fields/shapes the 2025-based contracts never saw** → found on dev before prod (Task 6); a contract change is made test-first.
5. **After `make destroy` → `make apply` the WIF provider name changes** (random pool suffix) → `make gh-vars` republishes it; documented in the README.

---

### Task 1: Robustness fixes carried over from Plan 3 review

**Files:**
- Modify: `projects/pitwall/transform/models/sources.yml`, `projects/pitwall/Makefile`, `projects/pitwall/README.md`

- [ ] **Step 1: Branch**

```bash
cd "/Users/tomasripsky/Data Engineering/Claude Code Enviroment"
git switch dev && git pull --ff-only
URL=$(gh issue create --title "feat(pitwall): CI/CD workflows and production environment" \
  --label "type:feat,project:pitwall" \
  --body "Plan 4 of pitwall: docs/superpowers/plans/2026-09-30-pitwall-4-cicd-prod.md")
git switch -c "feat/${URL##*/}-pitwall-cicd-prod"
git add docs/superpowers/plans/2026-09-30-pitwall-4-cicd-prod.md
git commit -m "docs(pitwall): add implementation plan 4 (CI/CD + prod)"
```

- [ ] **Step 2: Raw duplicates warn instead of blocking**

A duplicate returned by OpenF1 is removed by staging's dedup; blocking the scheduled prod run for it would be worse than the defect. In `transform/models/sources.yml`, add `config: {severity: warn}` to the uniqueness tests on raw tables (staging keeps them at `error`):
- `openf1_meetings.meeting_key`: replace `data_tests: [unique, not_null]` with

```yaml
            data_tests:
              - not_null
              - unique:
                  config:
                    severity: warn
```

- `openf1_sessions.session_key`: same replacement.
- the four `dbt_utils.unique_combination_of_columns` tests on `openf1_drivers`, `openf1_laps`, `openf1_stints`, `openf1_pit`: add under each, aligned with `arguments:`,

```yaml
              config:
                severity: warn
```

Run: `cd projects/pitwall/transform && export PITWALL_BQ_PROJECT=pitwall-tr-dev && uv run dbt parse --profiles-dir . && python3 -c "import json; m=json.load(open('target/manifest.json')); print(sorted({n['config']['severity'] for n in m['nodes'].values() if n['resource_type']=='test' and (n['name'].startswith('source_unique') or n['name'].startswith('dbt_utils_source_unique_combination'))}))"`
Expected: `['warn']`.

- [ ] **Step 3: Doc fixes from the review**

- `Makefile` bootstrap help: `ORG_ID=XXXXXXXXXXXX` → `ORG_ID=XXXXXXXXXXXX` (IDs live in `gcloud organizations list`, not in docs).
- `README.md` "Cost & teardown": "four BigQuery datasets" → "five BigQuery datasets (raw, staging, intermediate, marts, audit)".
- `CHANGELOG.md` `## [Unreleased]` → `### Added` (so it ships in v0.3.0): `- \`pitwall\`: CI (lint, tests, terraform validate, dbt in per-PR datasets) and a scheduled/manual pipeline via Workload Identity Federation; production environment backfilled 2023 → 2026.`

- [ ] **Step 4: Commit**

```bash
git add transform/models/sources.yml Makefile README.md ../../CHANGELOG.md
git commit -m "fix(pitwall): raw duplicates warn (staging dedups); doc fixes from review"
```

---

### Task 2: CI permissions and GitHub environments

**Files:**
- Modify: `projects/pitwall/infra/gcp/iam.tf`, `projects/pitwall/Makefile`

**Interfaces:**
- Produces: GitHub Environments `dev` and `prod`; environment variables `PITWALL_PROJECT`, `PITWALL_WIF_PROVIDER`, `PITWALL_SERVICE_ACCOUNT` (dev now, prod in Task 7); `make gh-vars ENV=…`.

- [ ] **Step 1: Let the dev pipeline account create CI datasets**

Append to `infra/gcp/iam.tf`:

```hcl
# CI (dev only) creates and drops its own per-PR datasets; bigquery.user grants datasets.create.
resource "google_project_iam_member" "pipeline_ci_datasets" {
  count   = var.env == "dev" ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = google_service_account.pipeline.member
}
```

Run: `cd projects/pitwall && make plan`
Expected: `Plan: 1 to add, 0 to change, 0 to destroy.` Then `terraform -chdir=infra/gcp apply -auto-approve -var env=dev -var project_id=pitwall-tr-dev` (US$0: an IAM binding).

- [ ] **Step 2: `make gh-vars`**

In the Makefile add `gh-vars` to `.PHONY` and, after `destroy`:

```make
gh-vars: init ## Publish ENV's project, WIF provider and service account to the GitHub environment ENV
	gh variable set PITWALL_PROJECT --env $(ENV) --body "$(PROJECT_ID)"
	gh variable set PITWALL_WIF_PROVIDER --env $(ENV) --body "$$($(TF) output -raw workload_identity_provider)"
	gh variable set PITWALL_SERVICE_ACCOUNT --env $(ENV) --body "$$($(TF) output -raw pipeline_service_account)"
```

- [ ] **Step 3: Create the environments**

```bash
REPO=TomasRipsky/data-engineering-lab
gh api -X PUT "repos/$REPO/environments/dev" >/dev/null
gh api -X PUT "repos/$REPO/environments/prod" --input - >/dev/null <<'EOF'
{"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
EOF
for b in dev main; do
  gh api -X POST "repos/$REPO/environments/prod/deployment-branch-policies" -f name="$b" -f type=branch >/dev/null
done
gh api "repos/$REPO/environments/prod/deployment-branch-policies" -q '[.branch_policies[].name]'
```

Expected: `["dev","main"]`.

Run: `make gh-vars ENV=dev && gh variable list --env dev`
Expected: three variables; `PITWALL_WIF_PROVIDER` ends in `/providers/github-actions`.

- [ ] **Step 4: Commit**

```bash
git add infra/gcp/iam.tf Makefile
git commit -m "feat(pitwall): let dev CI create per-PR datasets; publish WIF settings to GitHub envs"
```

---

### Task 3: CI workflow

**Files:**
- Create: `.github/workflows/pitwall-ci.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/pitwall-ci.yml`:

```yaml
name: pitwall-ci

on:
  pull_request:
    paths:
      - "projects/pitwall/**"
      - ".github/workflows/pitwall-*.yml"
  workflow_dispatch:

concurrency:
  group: pitwall-ci-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: true

permissions:
  contents: read

defaults:
  run:
    working-directory: projects/pitwall

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10
      - run: uv sync --locked
      - run: make lint
      - run: make test

  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: hashicorp/setup-terraform@v4
      - run: terraform -chdir=infra/gcp fmt -check -recursive
      - run: terraform -chdir=infra/gcp init -backend=false -input=false
      - run: terraform -chdir=infra/gcp validate

  dbt:
    # Fork PRs cannot mint OIDC tokens: skip (not fail) the job that needs GCP.
    if: github.event_name == 'workflow_dispatch' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    environment: dev
    permissions:
      contents: read
      id-token: write
    env:
      PITWALL_BQ_PROJECT: ${{ vars.PITWALL_PROJECT }}
      DBT_CI_SCHEMA: ci_pr_${{ github.event.pull_request.number || github.run_id }}
    steps:
      - uses: actions/checkout@v7
      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.PITWALL_WIF_PROVIDER }}
          service_account: ${{ vars.PITWALL_SERVICE_ACCOUNT }}
      - uses: google-github-actions/setup-gcloud@v3
      - uses: astral-sh/setup-uv@v10
      - run: uv sync --locked
      - name: Create per-PR datasets that expire on their own
        run: |
          for layer in staging intermediate marts audit; do
            bq --location=us-central1 mk --force --dataset \
              --default_table_expiration 86400 "$PITWALL_BQ_PROJECT:${DBT_CI_SCHEMA}_${layer}"
          done
      - name: dbt build against dev raw data
        working-directory: projects/pitwall/transform
        run: |
          cp profiles.yml.example profiles.yml
          uv run dbt deps
          uv run dbt build --target ci --profiles-dir .
      - name: Drop per-PR datasets
        if: always()
        run: |
          for layer in staging intermediate marts audit; do
            bq rm -r -f -d "$PITWALL_BQ_PROJECT:${DBT_CI_SCHEMA}_${layer}" || true
          done
```

- [ ] **Step 2: Lint the workflow locally**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/pitwall-ci.yml')); print(sorted(d['jobs']), d['jobs']['dbt']['permissions'])"`
Expected: `['dbt', 'python', 'terraform'] {'contents': 'read', 'id-token': 'write'}`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pitwall-ci.yml
git commit -m "ci(pitwall): lint, tests, terraform validate and dbt build in per-PR datasets"
```

---

### Task 4: Pipeline workflow

**Files:**
- Create: `.github/workflows/pitwall-pipeline.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/pitwall-pipeline.yml`:

```yaml
name: pitwall-pipeline

on:
  schedule:
    - cron: "0 6 * * 1" # Monday 06:00 UTC: the morning after a race weekend
  workflow_dispatch:
    inputs:
      env:
        description: Environment
        type: choice
        options: [dev, prod]
        default: dev
      mode:
        description: "latest = new races only; meeting/season = (re)ingest one; none = reload + transform only"
        type: choice
        options: [latest, meeting, season, none]
        default: latest
      value:
        description: Meeting key (mode=meeting) or year (mode=season)
        required: false
        default: ""

concurrency:
  group: pitwall-pipeline-${{ github.event_name == 'schedule' && 'prod' || inputs.env }}
  cancel-in-progress: false # never interrupt a run halfway through a load

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    environment: ${{ github.event_name == 'schedule' && 'prod' || inputs.env }}
    permissions:
      contents: read
      id-token: write
    env:
      TARGET_ENV: ${{ github.event_name == 'schedule' && 'prod' || inputs.env }}
      MODE: ${{ github.event_name == 'schedule' && 'latest' || inputs.mode }}
      VALUE: ${{ inputs.value }}
    defaults:
      run:
        working-directory: projects/pitwall
    steps:
      - name: Validate inputs before touching GCP
        working-directory: .
        run: |
          case "$MODE" in
            latest|none) ;;
            meeting|season)
              [[ "$VALUE" =~ ^[0-9]+$ ]] || { echo "::error::value must be a number for mode=$MODE, got '$VALUE'"; exit 1; } ;;
            *) echo "::error::unknown mode '$MODE'"; exit 1 ;;
          esac
      - uses: actions/checkout@v7
        with:
          # prod only ever runs released code
          ref: ${{ env.TARGET_ENV == 'prod' && 'main' || github.ref }}
      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.PITWALL_WIF_PROVIDER }}
          service_account: ${{ vars.PITWALL_SERVICE_ACCOUNT }}
      - uses: google-github-actions/setup-gcloud@v3
      - uses: astral-sh/setup-uv@v10
      - run: uv sync --locked
      - name: Ingest
        if: env.MODE != 'none'
        run: |
          case "$MODE" in
            latest) args="--latest" ;;
            *) args="--$MODE $VALUE" ;;
          esac
          make ingest ENV="$TARGET_ENV" ARGS="$args"
      - name: Load raw tables
        run: make load ENV="$TARGET_ENV"
      - name: Transform and test
        run: make transform ENV="$TARGET_ENV"
```

- [ ] **Step 2: Lint the workflow locally**

Run: `python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/pitwall-pipeline.yml')); print(list(d[True]), [s.get('name', s.get('uses')) for s in d['jobs']['run']['steps']])"`
Expected: `['schedule', 'workflow_dispatch']` and the step list starting with `Validate inputs before touching GCP`. (PyYAML reads the key `on` as `True`.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pitwall-pipeline.yml
git commit -m "ci(pitwall): add scheduled and manual ingest-load-transform pipeline"
```

---

### Task 5: Prove CI on its own PR

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin HEAD
gh pr create --base dev --title "feat(pitwall): CI/CD workflows and production environment" \
  --body "Closes #<issue>. Plan 4 of pitwall. Task 5 onwards is verified from this PR's CI run."
```

- [ ] **Step 2: Watch the CI run**

Run: `gh run watch --exit-status $(gh run list --workflow pitwall-ci.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId -q '.[0].databaseId')`
Expected: jobs `python`, `terraform`, `dbt` all succeed; the dbt log shows `PASS=… WARN=4 ERROR=0` (or `WARN=` including the raw-duplicate warns if any) and the auth step used WIF (no key).

- [ ] **Step 3: Nothing left behind**

Run: `bq ls --project_id=pitwall-tr-dev | grep ci_pr_ || echo "no CI datasets left"`
Expected: `no CI datasets left`.

If any job fails, debug with superpowers:systematic-debugging (typical causes: WIF condition vs `workflow_ref`, missing role, `uv sync --locked` drift) and fix with a commit on the branch; ledger each ruling.

- [ ] **Step 4: Review and merge**

Run the `pr-reviewer` agent on the branch with this plan's Review Focus; fix Critical/Important findings (test first where there is code); squash-merge once CI is green. The pipeline workflow can only be dispatched once it exists on the default branch (`dev`), which is why Task 6 follows the merge.

---

### Task 6: Pipeline on dev, including the 2023 contract check

- [ ] **Step 1: Input validation fails fast**

Run: `gh workflow run pitwall-pipeline.yml --ref dev -f env=dev -f mode=season -f value=abc` then watch it.
Expected: the run fails in `Validate inputs before touching GCP` with `value must be a number for mode=season`; no auth step ran.

- [ ] **Step 2: A real dev run (current season, new races only)**

Run: `gh workflow run pitwall-pipeline.yml --ref dev -f env=dev -f mode=latest` and `gh run watch --exit-status <id>`.
Expected: success. `Ingest` logs finished 2026 meetings (dev only held 2025), `Load` loads 12 tables, `Transform and test` ends `ERROR=0`. This proves pyarrow → GCS and dbt → BigQuery work with WIF credentials (external account), not only with Tomas's ADC.

If pyarrow's GCS client rejects the external-account credentials: pass a short-lived token instead (`GcsFileSystem(access_token=..., credential_token_expiration=...)` fed from `gcloud auth print-access-token`) — implement test-first in `lake.py` and ledger the ruling.

- [ ] **Step 3: The 2023 and 2024 seasons on dev**

Run, one after the other (the concurrency group keeps only one pending run):
`gh workflow run pitwall-pipeline.yml --ref dev -f env=dev -f mode=season -f value=2023`, watch; then the same with `2024`.
Expected: both succeed. If ingestion raises `ContractError` (a field shape 2025 never showed), reproduce it with a unit test in `tests/test_contracts.py`, fix the contract, and rerun — on this plan's branch via a new PR if Task 5 is already merged.

- [ ] **Step 4: Sanity on three seasons**

```bash
bq --project_id=pitwall-tr-dev query --use_legacy_sql=false \
  'select s.season, count(distinct s.session_key) races, countif(p.source = "stint_change") inferred_stops
   from marts.dim_sessions s left join marts.fct_pit_stops p using (session_key) group by 1 order by 1'
```

Expected: 2023 ≈ 28 sessions (22 races + 6 sprints), 2024 ≈ 30, 2025 = 30, 2026 so far; `inferred_stops` > 0 only where OpenF1 has no pit data (2023).

---

### Task 7: Production

- [ ] **Step 1: HARD STOP — confirm with Tomas**

"About to create GCP project `pitwall-tr-prod` inside `tomyripsky-org`, link billing, add a 5 EUR budget alert, and `terraform apply` the prod environment (bucket, 5 datasets, pipeline + dashboard service accounts, WIF restricted to environment `prod` on `dev`/`main`, 50 GiB/day query quota). Expected cost: 0/month. Then release v0.3.0 to `main` (prod only runs released code) and backfill 2023 → 2026 through the pipeline (~1 h of Actions time, free on public repos). Proceed?"

- [ ] **Step 2: Bootstrap and apply prod**

```bash
cd projects/pitwall
make bootstrap ENV=prod BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX ORG_ID=XXXXXXXXXXXX
make plan ENV=prod        # expect 28 to add: dev's 24 + dashboard SA, its marts viewer, job user and WIF binding (no CI role)
terraform -chdir=infra/gcp apply -auto-approve -var env=prod -var project_id=pitwall-tr-prod
make gh-vars ENV=prod && gh variable list --env prod
```

- [ ] **Step 3: Release v0.3.0 (lab release recipe)**

```bash
cd "/Users/tomasripsky/Data Engineering/Claude Code Enviroment"
git switch dev && git pull --ff-only
URL=$(gh issue create --title "chore(lab): release v0.3.0" --label "type:chore,project:lab" --body "pitwall pipeline: extractor, GCP infra, dbt marts, CI/CD.")
git switch -c "chore/${URL##*/}-release-v0.3.0"
```

In `CHANGELOG.md` rename `## [Unreleased]` to `## [0.3.0] - <today>` and add an empty `## [Unreleased]` above it. Then:

```bash
git commit -am "chore(lab): release v0.3.0"
git push -u origin HEAD
gh pr create --base dev --title "chore(lab): release v0.3.0" --body "Closes #${URL##*/}"
gh pr merge --squash --delete-branch
git switch dev && git pull --ff-only
gh pr create --base main --head dev --title "release: v0.3.0" --body "pitwall pipeline (plans 1–4)."
gh pr merge --merge          # merge commit, per the lab's release rule
gh release create v0.3.0 --target main --title "v0.3.0" --generate-notes
```

- [ ] **Step 4: Backfill prod through the pipeline**

For `2023`, `2024`, `2025`, `2026` in order: `gh workflow run pitwall-pipeline.yml --ref dev -f env=prod -f mode=season -f value=<year>` and watch each to success (~15 min each).
Expected: every run succeeds from the `prod` environment and checks out `main`. Then run the Task 6 Step 4 query against `pitwall-tr-prod`.

- [ ] **Step 5: The schedule is armed**

Run: `gh workflow view pitwall-pipeline.yml`
Expected: the workflow is active; next Monday 06:00 UTC it will run `--latest` on prod.

---

### Task 8: Decisions, docs, knowledge

**Files:**
- Create: `projects/pitwall/docs/decisions/0006-github-actions-as-orchestrator.md`
- Modify: `projects/pitwall/README.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-09-29-pitwall-design.md`

- [ ] **Step 1: ADR 0006**

```markdown
# 0006 — GitHub Actions as the orchestrator

- **Status:** Accepted
- **Date:** 2026-09-30

## Context
The pipeline has three sequential steps (ingest → load → transform), runs weekly, and must be
visible to portfolio readers, cost nothing and hold no keys.

## Decision
Two GitHub Actions workflows: `pitwall-ci` on PRs and `pitwall-pipeline` on a Monday cron plus manual
dispatch, authenticating to GCP through Workload Identity Federation and reusing the Makefile.

## Alternatives considered
- Cloud Composer (managed Airflow) — ~US$300+/month minimum.
- Dagster/Airflow self-hosted — needs somewhere to run and a database; overkill for one linear DAG.
- Cloud Run Jobs + Cloud Scheduler — nearly free and GCP-native, but more Terraform and invisible to readers.

## Consequences
- Free on a public repo; every run is public evidence of the pipeline working.
- Cron is best-effort (can be delayed) and disabled after 60 days without repo activity.
- No task-level retries or lineage UI; acceptable for three steps. Revisit when a project has real
  cross-pipeline dependencies.
```

- [ ] **Step 2: README**

In `projects/pitwall/README.md`:
- Tech stack row `Orchestration | GitHub Actions (cron + manual dispatch) | Free, public runs, WIF auth — [ADR 0006](docs/decisions/0006-github-actions-as-orchestrator.md)`;
- after "Run it" add:

```markdown
## CI/CD

| Workflow | When | What |
|---|---|---|
| `pitwall-ci` | every PR touching pitwall | lint + tests, `terraform validate`, `dbt build` in throwaway `ci_pr_<n>_*` datasets (dropped afterwards, 1-day expiry as a safety net) |
| `pitwall-pipeline` | Mondays 06:00 UTC (prod) and on demand | ingest → load → transform; prod runs code from `main` only |

GCP access uses Workload Identity Federation: no keys exist. Each GitHub Environment (`dev`, `prod`)
holds its project, WIF provider and service account as variables — `make gh-vars ENV=…` republishes
them after `make apply` (the provider name changes after a destroy/apply cycle).

On-demand runs: **Actions → pitwall-pipeline → Run workflow**, or
`gh workflow run pitwall-pipeline.yml -f env=prod -f mode=season -f value=2024`
(`mode=none` reloads and rebuilds models without calling the API).

GitHub disables scheduled workflows after 60 days without repository activity (it can happen in the
December–February off-season): re-enable it from the Actions tab.
```

- [ ] **Step 3: Spec**

Spec §7: add "`mode=none` reloads and transforms without ingesting." and "Per-PR datasets include `ci_pr_<n>_audit` (store_failures)." Roadmap note in the spec header: "Dashboard (§8) is delivered by Plan 5."

- [ ] **Step 4: Commit, PR, merge**

Commit docs on a `docs/<issue>-pitwall-cicd-docs` branch (the Plan 4 PR is already merged), PR into `dev`, squash-merge once `pitwall-ci` is green.

- [ ] **Step 5: Second brain**

Enrich `03 - Production/CI CD.md` (path filters vs required checks, `workflow_dispatch` only from the default branch, environments + deployment branch policies, concurrency groups, `if: always()` cleanup) and `03 - Production/Workload Identity Federation.md` (the GitHub side: `id-token: write`, `workflow_ref` conditions, forks can't mint tokens). Update `07 - Laboratory/pitwall.md` → next: Plan 5 (dashboard). Commit and push the vault.
