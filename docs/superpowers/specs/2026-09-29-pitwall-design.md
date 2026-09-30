# pitwall — Design

- **Date:** 2026-09-29
- **Status:** Approved in brainstorming; awaiting written-spec review.
- **Issue:** #12
- **Scope:** First data project of the lab. A batch ELT pipeline over Formula 1 data that answers race-strategy questions through a public dashboard. Telemetry is phase 2 (Section 11).

## 1. Intent

- **Purpose:** learning + public portfolio. The project must demonstrate engineering judgment (idempotency, backfill, contracts, least privilege, cost control), not tool collection.
- **Audience:** recruiters and engineers who likely know nothing about F1 — and neither does Tomas. Every model, column and dashboard page explains what it shows in plain language.
- **Story:** "How do F1 teams win races with tyres and pit stops?" — stint timelines, tyre degradation, and whether the undercut works.

**Success criteria**
1. A public dashboard on GitHub Pages shows every Race and Sprint session from 2023 to the latest completed Grand Prix.
2. After a race weekend, the Monday scheduled run ingests the new Grand Prix and republishes the dashboard with no manual step.
3. Re-running any ingestion for the same Grand Prix produces identical warehouse contents (idempotent).
4. A full backfill of 2023 → current season runs with one command, within the API rate limit.
5. CI on every PR runs lint, Python tests, `terraform validate`, `dbt build` in an ephemeral BigQuery dataset, and an Evidence build — green before merge.
6. Running cost is US$0/month; a budget alert and a BigQuery query quota exist before the first deploy.
7. `make destroy ENV=dev` has been run successfully and `make apply ENV=dev` restores a working environment.
8. Someone with no F1 knowledge can read any dashboard page and explain what it shows (glossary + "What am I looking at?" boxes).

## 2. F1 glossary (used throughout; also shipped in the README and dashboard)

| Term | Meaning |
|---|---|
| **Meeting / Grand Prix (GP)** | One race weekend at one circuit (e.g. Italian GP at Monza). Contains several sessions. |
| **Session** | One on-track event of a meeting: practice, qualifying, **Sprint** (short Saturday race) or **Race** (main Sunday race). |
| **Lap** | One full tour of the circuit. Lap time is split into three **sectors**. |
| **Compound** | Tyre type. SOFT (fastest, wears quickly), MEDIUM, HARD (slowest, lasts longest), INTERMEDIATE and WET (rain). |
| **Stint** | The laps a driver completes on one set of tyres, between two pit stops. |
| **Tyre age** | Laps already driven on a set of tyres (sets can be reused from earlier sessions). |
| **Degradation** | How much slower a car gets per lap as its tyres wear, in seconds per lap. |
| **Pit stop** | Stop in the pit lane to change tyres. ~2–3 s stationary, ~20 s lost overall. |
| **Undercut** | Pitting *before* the rival just ahead; fresh tyres make you faster, so you are ahead when they pit. The **overcut** is the opposite. |
| **Safety Car (SC) / Virtual Safety Car (VSC)** | After an incident, all cars must drive slowly. Pitting then costs less time. |
| **Grid** | Starting order of a race, decided mostly by qualifying. |

## 3. Architecture

```
OpenF1 API ──► extractor (Python) ──► lake: raw Parquet ──► BigQuery ──► dbt ──► Evidence ──► GitHub Pages
 REST, 30 req/min    httpx + limiter     GCS bucket per env     raw tables   staging →   static site,
                     + retries           (hive-style paths)     (full        intermediate built from
                                                                reload)      → marts     prod marts
                     └──────────── GitHub Actions: CI on PRs · scheduled pipeline · Pages deploy ────────────┘
```

- **Source:** [OpenF1](https://openf1.org) — free historical data from 2023, no API key, 3 req/s and 30 req/min on the free tier, educational/non-commercial use. Live data (paid) is not needed.
- **Environments:** two GCP projects, `pitwall-dev` and `pitwall-prod`, with identical resources. Dev and prod both run in the cloud (dev/prod parity). The code may run from Tomas's laptop against dev using `gcloud` user credentials.
- **Region:** `us-central1` for the bucket and BigQuery datasets (GCS free tier applies only to some US regions; GCS→BigQuery loads require co-located resources).
- **Portability:** the extractor only knows a lake URI (`gs://...` or `file://...`) through `pyarrow.fs`; the warehouse layer is the only GCP-specific part besides Terraform. Porting to AWS means S3 + a warehouse adapter + a Terraform root, recorded in an ADR.

**Repository layout** (created from `projects/_template` via `/new-project`):

```
projects/pitwall/
├── src/pitwall/          # extractor + loader + CLI (argparse)
├── tests/                # pytest, fixtures/ with recorded API responses
├── transform/            # dbt project (dbt-bigquery)
├── dashboard/            # Evidence project
├── infra/gcp/            # Terraform root: main.tf, variables.tf, dev.tfvars, prod.tfvars
├── docs/decisions/       # project ADRs
├── Makefile              # setup, test, lint, ingest, load, transform, apply, destroy, bootstrap
└── README.md             # architecture diagram, glossary, run, cost & teardown, what I learned
```
Workflows live in the repo root `.github/workflows/` (`pitwall-ci.yml`, `pitwall-pipeline.yml`), path-filtered to `projects/pitwall/**`.

## 4. Ingestion

**Scope (v1).** Only sessions of type Race and Sprint.

| Level | Endpoints |
|---|---|
| Per season | `meetings`, `sessions` |
| Per meeting | `starting_grid` (attached to the *qualifying* sessions, so fetched by `meeting_key`) |
| Per session | `drivers`, `laps`, `stints`, `pit`, `position`, `weather`, `race_control`, `session_result`, `overtakes` |

Race and Sprint sessions are `session_type == "Race"` (verified: `session_name` is `Race` or `Sprint`); sessions with `is_cancelled == true` are ignored. Meetings without such sessions (e.g. pre-season testing) are never ingested.

Out of v1: `car_data`, `location`, `intervals` (phase 2), `team_radio`, `championship_drivers`, `championship_teams`.

**Unit of work = one meeting.** CLI (`pitwall ingest`), one code path, three selectors:
- `--meeting <meeting_key>` — (re)ingest one GP; overwrites its partition.
- `--latest` — the scheduled mode: ingests every meeting of the current season whose last Race/Sprint session ended more than 6 h ago and has no success marker in the lake.
- `--season <year>` — backfill all meetings of a season.

Every run first refreshes the season-level files (`meetings`, `sessions`) for the seasons it touches.

**Request budget.** ~9 requests per session plus 1 per meeting, ~1.25 Race/Sprint sessions per meeting, ~24 meetings per season → ~400 requests per season ≈ 15 min at 30 req/min. Full backfill 2023 → 2026 ≈ 1 h, run once.

**Lake layout** (root from env var `PITWALL_LAKE_URI`, e.g. `gs://pitwall-dev-raw`):

```
raw/meetings/season=2025/part.parquet
raw/sessions/season=2025/part.parquet
raw/<endpoint>/season=2025/meeting_key=1254/part.parquet      # all sessions of that meeting
raw/_success/season=2025/meeting_key=1254.json                # written last; manifest
```

- Each record gains `_ingested_at` (UTC timestamp). The manifest lists row counts per endpoint (its keys are the endpoints the loader may read), the request count and `_ingested_at`; request URLs are reproducible from the path and were dropped.
- **Atomicity:** GCS has no atomic rename, so a meeting is visible only once its `_success` marker exists. A crashed run leaves files without a marker; they are ignored by the loader and overwritten by the next run. A single object write is atomic, so season-level files need no marker.
- **Idempotency:** re-ingesting a meeting rewrites the same object paths and the same marker.
- **State:** the lake is the state (which markers exist). No separate state store.

**Schema contract.** One explicit `pyarrow` schema per endpoint in code.
- A required column missing → the run fails.
- An unknown new column → warning, column dropped until it is added to the contract by PR (schema evolution is a reviewed decision).
- Types are cast to the contract; a failed cast fails the run.

## 5. Loading to BigQuery

`pitwall load` rebuilds each raw table (`raw.openf1_<endpoint>`) with one load job per endpoint, `WRITE_TRUNCATE`, from an **explicit list of URIs** built from the success markers (never a wildcard, so unmarked partial files cannot leak in).

Rationale: v1 data is megabytes. A full reload is atomic, idempotent, free (load jobs cost nothing) and trivial to reason about. Partition-level loads are deferred to phase 2, where telemetry volume justifies them.

## 6. Transformation (dbt)

dbt project in `transform/`, adapter `dbt-bigquery`, packages: `dbt_utils`. Every model and column has a plain-language `description`; each mart states its grain in its description.

**Layers**
- **staging** — `stg_openf1__<endpoint>`: one-to-one with raw tables; typing, clean names, dedup on the natural key. No business logic. `weather` and `overtakes` stay as sources without staging models until a page needs them; columns OpenF1 never fills (`drivers.country_code`, `race_control.qualifying_phase` in races) are not carried over.
- **intermediate** — `int_neutralised_laps` (SC/VSC laps from race-control messages; a period without an end message runs to the lap before the next deployment of the same type, or to the session's last lap) and `int_laps_enriched`: each lap with compound, tyre age, pit-in/pit-out flags, SC/VSC flag and running order at the end of the lap.
- **marts**

| Model | Grain (one row =) | Purpose |
|---|---|---|
| `dim_meetings` | one Grand Prix | circuit, country, dates |
| `dim_sessions` | one session | Race/Sprint, start/end times |
| `dim_session_drivers` | one driver in one session | name, team, team colour (drivers change teams across seasons) |
| `fct_laps` | one lap of one driver in one session | lap and sector times, compound, tyre age, position, flags |
| `fct_stints` | one stint | compound, laps, mean pace, degradation slope (s/lap) |
| `fct_pit_stops` | one pit stop | duration, lap, compound before/after, position before/after |
| `fct_undercut_attempts` | one pit stop that qualifies as an undercut attempt | success flag |
| `fct_session_results` | one driver in one finished session | grid vs finishing position |

**Degradation slope:** slope of a least-squares fit of lap time on tyre age within a stint, excluding pit-in/pit-out laps and SC/VSC laps; null when fewer than 5 clean laps remain. A clean lap also excludes laps slower than 1.2 × the session median (red flags, damage). Fuel burn makes cars ~0.03–0.06 s/lap faster, so the slope under-states tyre wear; documented, not corrected. Stints with missing or inverted lap ranges are excluded from `fct_stints`.

**Pit stops:** sessions with no pit data (some 2023 races) infer stops from consecutive stints (`source = 'stint_change'`).

**Undercut attempt (documented simplification):** driver A pits on lap *n* while in position *p+1* at the end of lap *n−1*, directly behind driver B in position *p*; B pits within laps *n+1 … n+3*. **Success** = A is ahead of B at the end of B's out-lap (B's pit lap + 1), the first lap on which both have completed their stops. Uses only `position` and `pit`; ignores time gaps (`intervals`) and SC/VSC context — stated as a limitation in the model description and on the dashboard.

**Schemas/datasets**
- dev and prod: datasets `staging`, `intermediate`, `marts` in their own project, plus `audit` for failing test rows (`store_failures`).
- CI: `ci_pr_<n>_staging`, `ci_pr_<n>_intermediate`, `ci_pr_<n>_marts` in `pitwall-dev`, reading dev's `raw` dataset (so dev must hold at least one ingested season); dropped at the end of the job, and created with a 1-day default table expiration as a safety net if the drop step never runs.

## 7. Orchestration and CI/CD (GitHub Actions)

All GCP access uses **Workload Identity Federation** — no service-account keys anywhere.

**`pitwall-ci.yml`** — on PRs touching `projects/pitwall/**`:
1. `ruff check`, `ruff format --check`, `pytest` (no cloud access).
2. `terraform fmt -check`, `terraform validate`.
3. `dbt build` into the `ci_pr_<n>_*` datasets; a final step with `if: always()` drops them.
4. `evidence build`.

**`pitwall-pipeline.yml`** — scheduled and manual:
- Triggers: cron `0 6 * * 1` (Monday 06:00 UTC) → prod `--latest`; `workflow_dispatch` with inputs `env` (dev|prod) and `mode` (`latest` | `meeting=<key>` | `season=<year>`).
- Steps: `ingest` → `load` → `dbt build` → `evidence build` → deploy to GitHub Pages (prod only).
- Steps are sequential: if dbt tests fail, the dashboard is not redeployed and the last good version stays online. GitHub emails on workflow failure.
- **Prod runs released code:** prod jobs check out `main`; they run in the GitHub Environment `prod`, and the prod WIF provider only accepts tokens from that environment.
- A push to `main` touching `projects/pitwall/**` (i.e. a release) runs only `dbt build` → `evidence build` → deploy, so released dashboard and model changes go live without re-ingesting.

**Known limitation:** GitHub disables scheduled workflows in public repos after 60 days without repository activity (possible in the Dec–Feb off-season). Documented in the README with the one-click re-enable; no keep-alive hack.

## 8. Dashboard (Evidence on GitHub Pages)

Evidence project in `dashboard/`, reading `pitwall-prod` marts at build time with the read-only `dashboard` service account. The published site is static: visitors never reach BigQuery. Text is in English. Every page opens with a **"What am I looking at?"** box.

1. **Home** — what the site is, the glossary, season selector, latest GP summary.
2. **Race strategy** — pick a GP: one horizontal bar per driver, segmented by stint and coloured by compound, pit stops marked, finishing order.
3. **Tyre degradation** — pace vs tyre age by compound, filterable by circuit ("how long does a SOFT last at Monaco vs Bahrain?").
4. **Undercut** — success rate by season, circuit and team, plus the list of attempts, with the definition and its limitations.

## 9. Infrastructure, security, cost, teardown

**Bootstrap (manual, once, scripted as `make bootstrap`):** create projects `pitwall-tr-dev` and `pitwall-tr-prod` inside the organization (`ORG_ID`; project IDs are global; only dev exists before Plan 4), link billing, enable APIs, and create the **billing budget alert (5 in the billing account's currency — EUR here; 50/90/100%) before any Terraform resource**. Project creation stays out of Terraform (needs org/billing-level permissions not worth managing here).

**Terraform** — one root in `infra/gcp/`, variable `env`, `dev.tfvars` / `prod.tfvars`, **local state with one workspace per env** (only Tomas applies; migrate to remote state via ADR if CI ever applies). Per environment:
- Bucket `pitwall-<env>-raw`, uniform bucket-level access, `force_destroy = true`.
- BigQuery datasets `raw`, `staging`, `intermediate`, `marts`, `audit` (`us-central1`), with `delete_contents_on_destroy`.
- Service accounts: `pipeline` (write bucket, BigQuery data editor + job user) and, in prod only, `dashboard` (data viewer on `marts` + job user).
- Workload Identity Pool (ID with a random suffix: deleted pools stay reserved 30 days) + GitHub OIDC provider whose `attribute_condition` pins the immutable repository ID of `TomasRipsky/data-engineering-lab` (prod: additionally `environment == "prod"`).
- **BigQuery custom quota** on query bytes per day (50 GiB, via the `google-beta` provider; default is 200 TiB) — a budget alert only warns; a quota stops spending.

**Secrets:** none. Project IDs and WIF provider names are GitHub *variables*. gitleaks keeps running on every commit.

**Cost:** expected US$0/month (MB-scale storage, tiny queries, free Actions and Pages for public repos). Confirmed again with Tomas before the first `terraform apply`.

**Teardown:** `make destroy ENV=dev|prod` runs `terraform destroy`. `force_destroy` on buckets is deliberate: the lake is fully regenerable from the API. Nuclear option documented: `gcloud projects delete`. The destroy → apply cycle is tested on dev before prod is left running.

## 10. Error handling and testing

**Errors**
- **Client-side rate limiter** keeps requests under 30/min (prevent, don't react).
- **Retries:** exponential backoff with jitter on 429, 5xx and network errors, max 5 attempts, honouring `Retry-After`. Other 4xx fail fast. Every request has a timeout.
- **"No data" is HTTP 404** with body `{"detail": "No results found."}` (verified). The client maps exactly that response to an empty list; any other 404 fails.
- **Data not yet available:** if `laps` or `stints` return empty for a session considered finished, the meeting is skipped with a warning (no marker written) and retried on the next run; the run does not fail.
- **Empty optional endpoints** are valid and written as empty files with the contract schema. Real example: `pit` has no data for some 2023 races (e.g. Bahrain 2023, session 7953); dbt must tolerate it (pit stops can be derived from stint changes — decided in the dbt plan).

**Testing**
- **Extractor (TDD, pytest):** rate limiter, retry policy, path building, schema contract, marker logic — using `httpx.MockTransport` (no extra mocking library). An integration test runs `ingest --meeting` end to end against a temporary `file://` lake with small recorded JSON fixtures from one real GP.
- **dbt:** generic tests (`unique`, `not_null`, `relationships`, `accepted_values` for compounds and session types); a grain test on every mart (`dbt_utils.unique_combination_of_columns`); **dbt unit tests** for undercut detection and degradation slope with hand-built cases; singular tests (laps within a stint are contiguous; every pit stop falls between two stints).
- **Sanity checks** (severity `warn`): lap times within a plausible range, excluding pit and SC/VSC laps.
- **Data quality (dbt source tests):** ingestion rejects only structural breakage; semantic rules live in dbt. `error` for impossible values that would corrupt marts (null/duplicate keys, out-of-range positions/points/grid, non-positive lap times) — blocks the marts and therefore the dashboard; `warn` for unusual-but-real data (null-rate expectations per session, unknown compounds, long pit-lane times, fewer than 18 drivers with laps). Failing rows of every test are stored in the `audit` dataset (`store_failures`). Expected empty fields and known source defects are documented in the README.
- **Dashboard:** `evidence build` in CI.

## 11. Phase 2 and out of scope

- **Phase 2 — telemetry:** `car_data` (~3.7 Hz; ~500k rows per race) and `location`, with partition-level loads (integer-range or time partitioning + clustering), speed-trace and braking-point pages. Gets its own spec.
- Out of scope for v1: live data, qualifying and practice analytics, championship standings, team radio, other clouds, any orchestrator beyond GitHub Actions, historic data before 2023 (e.g. Jolpica/Ergast).

## 12. ADRs to write (project `docs/decisions/`)

1. OpenF1 as data source (vs OpenSky flights: no REST backfill; better suited to the streaming project).
2. Lake-first custom extractor (vs dlt; vs direct-to-warehouse ELT).
3. GCP with two projects; BigQuery-only with ephemeral CI datasets (DuckDB dropped: dual SQL dialects are a permanent tax once dev lives in the cloud).
4. GitHub Actions as orchestrator (vs Cloud Run Jobs, Dagster, Composer).
5. Evidence on GitHub Pages (vs Looker Studio, Streamlit).
6. Full reload of raw tables in v1.
7. `force_destroy` on lake buckets.

## 13. Risks and items to verify before/while planning

| Item | Check | Fallback |
|---|---|---|
| Evidence BigQuery connector with WIF / Application Default Credentials | Context7 / Evidence docs | Export marts to Parquet in the pipeline; Evidence reads the files |
| ~~OpenF1 session filter for Race + Sprint~~ | Resolved: `session_type == "Race"` covers both | — |
| ~~Response size per session~~ | Resolved: largest (`laps`) ≈ 500 KB per race | — |
| Lab `.gitignore` ignores `*.tfvars` | Plan 2 | Commit `*.tfvars.example` or pass `-var` from the Makefile |
| GitHub Pages is one site per repo (`tomasripsky.github.io/data-engineering-lab/`) | Evidence `basePath` config | A second project needing Pages triggers a lab-level ADR (combined site or separate repo) |
| ~~BigQuery custom quota settable via Terraform~~ | Resolved: `google_service_usage_consumer_quota_override` (google-beta), metric `bigquery.googleapis.com/quota/query/usage`, limit `/d/project`, MiB | — |
| ~~pyarrow `create_dir` on GCS~~ | Resolved: it can create buckets, so the lake only calls it on local filesystems | — |
