# pitwall — How it works

The walkthrough: read this after the [README](../README.md) to understand the insides. Written during the tutor reviews, so every section explains *why*, not only *what*, and ends with an **In short** summary in plain words — read those alone for a quick refresher.

## Read this first

1. [`src/pitwall/cli.py`](../src/pitwall/cli.py) — the three commands (`ingest`, `load`, `site-export`) and the environment variables that point them at a lake and a GCP project.
2. [`src/pitwall/ingest.py`](../src/pitwall/ingest.py) — the unit of work (one Grand Prix) and the marker dance that makes re-runs safe.
3. [`src/pitwall/contracts.py`](../src/pitwall/contracts.py) — what the API is allowed to send us.
4. [`transform/models/`](../transform/models/) — staging → intermediate → marts; each mart states its grain.
5. [`.github/workflows/pitwall-pipeline.yml`](../../../.github/workflows/pitwall-pipeline.yml) — how the whole thing runs on Mondays in prod.

## Architecture

- **OpenF1 API** — free REST API with F1 timing data from 2023. No key, 30 requests/min. It hands us JSON lists, one endpoint per kind of fact (laps, stints, pit stops…).
- **`pitwall ingest`** — a Python extractor. Picks which Grands Prix to fetch, calls the API politely, validates every record against a contract and writes Parquet. Hands the lake one folder per endpoint and Grand Prix, plus a success marker.
- **Raw lake** — Parquet files on GCS (`gs://pitwall-tr-<env>-raw`), or a local folder offline. The replayable source of truth: everything downstream can be rebuilt from it without calling the API again.
- **`pitwall load`** — rebuilds each BigQuery `raw.openf1_<endpoint>` table from the marked files, in full.
- **dbt** — SQL models in BigQuery: staging (clean names and types) → intermediate (racing rules) → marts (one table per question, with a stated grain), tested on every build.
- **`site-export`** — queries the marts and writes six small Parquet files for the lab site.
- **Lab site** — Observable Framework, static, on GitHub Pages. Never touches BigQuery.

## Components explained

### Ingestion (`client.py`, `contracts.py`, `ingest.py`, `lake.py`)

A Python extractor (httpx + pyarrow) that moves OpenF1 into a Parquet lake with three design properties: **politeness** to the API, a schema **contract** at the boundary, and **idempotency** per Grand Prix. It is the foundation: if the lake is right, everything downstream can be rebuilt from it.

**Unit of work = one Grand Prix (a *meeting*).** Every selector reduces to "ingest these meetings": `--meeting 1255` is one, `--season 2024` is every finished meeting of a year, `--latest` is finished meetings with no success marker yet. One code path means the backfill and the Monday run cannot drift apart.

What a scheduled run (`pitwall ingest --latest`) does:

```
cli.main ─► ingest_latest
   ├─ lake.markers()                    ← which Grands Prix are done? (the lake IS the state)
   ├─ for each year (current + previous during its first 45 days):
   │    refresh_season  → GET meetings?year=, GET sessions?year=  → raw/<ep>/season=Y/part.parquet
   │    finished_meetings(now)          ← last race session ended ≥ 6 h ago
   │    for each finished meeting without a marker:
   │        ingest_meeting:
   │          1. GET 9 endpoints × every Race/Sprint session   (all in memory)
   │          2. to_table() checks the contract               (a failure writes nothing)
   │          3. delete marker → write Parquet files → write marker
   └─ a meeting still empty 3 days after its race → RuntimeError (red run)
```

#### 1. The client: prevent before reacting ([`client.py`](../src/pitwall/client.py))

- **Rate limiter (prevent).** OpenF1 allows 30 requests/min. `RateLimiter.wait()` guarantees 2.1 s between requests (30/min plus a margin). It measures with `time.monotonic()`, not `time.time()`: the wall clock can jump (NTP sync, daylight saving) — backwards would make the limiter sleep too long, forwards would let a burst through. The monotonic clock only moves forward.
- **Retries (react).** First classify: 429, 5xx and network errors are transient → retry. Any other 4xx means *our* request is wrong → fail at once (retrying would only hide the bug). The wait is `2^attempt + random()` seconds, capped at 60 s, honouring `Retry-After`. The `random()` is *jitter*: a thousand clients failing together would otherwise retry in the same second (thundering herd).
- **The 404 that is not an error.** OpenF1 answers "no data" with HTTP 404 and the exact body `{"detail": "No results found."}`. Treating every 404 as an error would break Grands Prix without pit data; treating every 404 as empty would hide a mistyped URL. Only that exact body becomes `[]`.
- **`sleep` and `clock` are constructor parameters** — dependency injection without a framework. Tests pass a fake clock, so a 60 s backoff is tested in microseconds.
- **Limit to keep in mind:** the limiter is in-memory state of *one process*. Two pipelines in parallel would each respect 30/min and send 60/min together. The workflow's `concurrency` group prevents that; a fleet of workers would need a shared token bucket (e.g. Redis).

#### 2. The contract: the boundary with what we don't control ([`contracts.py`](../src/pitwall/contracts.py))

The API belongs to someone else and may change tomorrow. One explicit `pyarrow` schema per endpoint, with three rules:

| What arrives | What we do | Why |
|---|---|---|
| A required field is missing (`session_key`, `lap_number`…) | **Fail the run** | Without keys, everything downstream is corrupt |
| A new field appears | **Warn and drop it** | Schema evolution is a decision reviewed in a PR, not an accident |
| A value doesn't cast to its type | **Fail the run** | Red today beats silent garbage on the dashboard |

- `1.0` is accepted as an int and `1.5` is not: the API sometimes sends whole numbers as floats.
- In Python `True` *is* an `int` (`isinstance(True, int)` is `True`); without the explicit check a boolean would slip into a numeric column as `1`.
- `gap_to_leader` arrives as `0`, `11.097` or `"+1 LAP"`, so it is stored as text — an explicit decision, not a patch.
- Each row is stamped with `_ingested_at`. `level` says how an endpoint is fetched: by `year` (meetings, sessions), by `meeting_key` (starting grid, attached to qualifying) or by `session_key` (everything else).
- **Ingestion rejects only what is structurally broken.** Odd-but-possible values (a 22-minute pit stop under a red flag) are judged in dbt, where there is context to judge them.

#### 3. Idempotency and atomicity: the marker ([`ingest.py`](../src/pitwall/ingest.py))

**What a marker is.** A tiny file written *last*, whose only job is to say "the files of this Grand Prix are complete and consistent — you may read them". Think of the "order ready" ticket in a kitchen: the dishes may already be on the counter, but the waiter only takes them when the ticket is up. Also called a *success file*, *done file* or *sentinel* (Hadoop and Spark write `_SUCCESS`).

**Why we need one.** A folder of files cannot tell a reader whether it is finished. If the process dies after writing `laps` and before `stints`, the folder looks normal but is half old, half new. A local disk solves this by writing to a temp folder and renaming it in one atomic step; **GCS has no atomic folder rename** (a "folder" is only a name prefix). What GCS *does* guarantee is that **a single object write is atomic**: a reader sees the whole old object or the whole new one, never half. The marker turns that single-object guarantee into a guarantee for the whole group:

```python
lake.delete(marker)                      # 1. "this Grand Prix is not trustworthy right now"
for endpoint, table in tables.items():
    lake.write_table(...)                # 2. overwrite deterministic paths
lake.write_json(marker, {...manifest})   # 3. "ready" — one object, written atomically
```

| Crash at… | What the lake holds | What readers do |
|---|---|---|
| before 1 | the previous good version + marker | read the previous version |
| between 1 and 3 | a mix of old and new files, **no marker** | ignore this Grand Prix; the next run overwrites it |
| after 3 | the new version + marker | read the new version |

Ours is also a **manifest**: it lists row counts per endpoint and the sessions included. The real one for the 2025 Grand Prix 1255 (Race + Sprint), at `raw/_success/season=2025/meeting_key=1255.json`:

```json
{
  "ingested_at": "2026-09-29T21:08:44.406830+00:00",
  "meeting_key": 1255,
  "requests": 19,
  "rows": {"drivers": 40, "laps": 1446, "overtakes": 269, "pit": 26, "position": 575,
           "race_control": 87, "session_result": 40, "starting_grid": 40, "stints": 66, "weather": 238},
  "season": 2025,
  "session_keys": [9993, 9998]
}
```
 The loader uses it as the list of files it may read (next block), and `--latest` uses the *existence* of markers as the list of what is done.

- **Idempotent** because paths are deterministic (`meeting_key=1255/part.parquet`): re-ingesting overwrites instead of appending, and duplicates come from appends.
- **Validate everything in memory before writing.** If `laps` is still empty (OpenF1 hasn't published yet), `ingest_meeting` returns `False` *without touching the lake*: the previous good version stays intact.

Edge decisions:
- **`SETTLE_TIME = 6 h`** — a race that just ended is not ingested: OpenF1 needs time to publish.
- **`LOOKBACK = 45 days`** — on 2 January the previous season is still scanned, so a December race is not lost at New Year.
- **`STALE_AFTER = 3 days` → red run** — a meeting still empty fails the run, *after* the others are ingested. Skipping silently forever is the worst failure mode: nobody finds out.
- `refresh_season` **never overwrites a file with an empty answer**: the loader reloads season files in full, so one flaky "No results" would empty the season in BigQuery.

#### 4. The lake: one abstraction, two worlds ([`lake.py`](../src/pitwall/lake.py))

`pyarrow.fs` hides local disk vs GCS; the rest of the code only sees relative paths, and `PITWALL_LAKE_URI=.lake` runs everything offline.
- **Hive-style paths (`season=2025/meeting_key=1255/`)**: any engine (BigQuery, Spark, DuckDB) reads them as partitions. `read_table` opens a file handle on purpose, so pyarrow does *not* invent `season` / `meeting_key` columns.
- **`create_dir` only on local disk**: object stores have no directories, and `create_dir` on GCS can create *buckets*.
- **The lake is the state.** No database remembers "last successful run": what is done is literally which markers exist, and that source of truth cannot drift from itself.

#### Alternatives rejected ([ADR 0002](decisions/0002-lake-first-custom-extractor.md))

- **dlt** — far less code and schema inference; the right call for a team that must ingest 20 APIs *now*. Rejected because it hides exactly what this project exists to teach.
- **API → BigQuery directly** — simplest, but without a lake every model change re-hits the API (~15 min per season) and extraction is tied to one warehouse. With the lake, porting to AWS is changing the URI to `s3://`.
- **Airbyte / Fivetran** — for standard sources (Postgres, Salesforce); OpenF1 has no connector and the cost isn't justified.

#### Where else it applies

- Marker written last: Spark `_SUCCESS`, Delta Lake / Iceberg commits (the transaction log is a sophisticated marker), atomic `mv` in deployments.
- Contract at the boundary: any system consuming third-party data (webhooks, CDC).
- Injecting the clock: anything with time in it (TTLs, schedulers, token expiry).

> **In short.** We ask the API slowly and politely, and retry only when the fault is temporary. Everything that comes back is checked against a list of expected fields and types. Each Grand Prix is saved as a group of files, and a small "ready" file (the marker) is written last — so anyone reading only trusts complete groups, and running it again just overwrites the same files. The lake of files is the memory of what's done; everything after it can be rebuilt from it without calling the API again.

### Loading into BigQuery (`load.py`)

`pitwall load` rebuilds the twelve `raw.openf1_<endpoint>` tables from the lake, **in full, every time**: one BigQuery load job per table, `WRITE_TRUNCATE`, from an explicit list of files built from the success markers. It is the bridge between files (the lake) and tables (the warehouse), and it adds no logic of its own: raw tables mirror the lake exactly.

```
lake.manifests()                   ← read every marker (85 Grands Prix in dev today)
   │
load_plan()  → {"openf1_laps": [gs://…/laps/season=2023/meeting_key=1140/part.parquet, …],
   │            "openf1_sessions": [gs://…/sessions/season=2023/part.parquet, …], …}
   │            season files: one per season that has markers · meeting files: one per marker
   │            that lists that endpoint
load()  → for each table: bigquery_loader(table, uris)
   │                          └─ client.load_table_from_uri(uris, "raw.openf1_laps",
   │                                  source_format=PARQUET, write_disposition=WRITE_TRUNCATE)
   └─ 12 load jobs, one after the other → rows per table in the log
```

#### 1. Full reload: throw it all away and rebuild ([ADR 0004](decisions/0004-full-reload-of-raw-tables.md))

Every run replaces each table with *everything* the lake holds, not just the new Grand Prix. It sounds wasteful; at our size it is the best option:

- **Size:** the biggest raw table (`openf1_laps`, 2023 → today) is ~104k rows and ~11 MB. Reloading it takes seconds.
- **Price:** batch load jobs are **free** in BigQuery (they run on a shared pool of compute), unlike queries (billed by bytes read) and streaming inserts (billed by volume).
- **Idempotent by construction:** the result depends only on what the lake holds, never on what the table held before. Run it twice, get the same table. An incremental load has to answer "what is new?", and every wrong answer is a duplicate or a gap.
- **Self-healing:** a re-ingested Grand Prix (upstream correction) or a deleted one is picked up automatically on the next load; no "update" or "delete" logic exists.

**Atomic per table.** BigQuery's own guarantee: truncation and loading "occur as one atomic update upon job completion". While the job runs, readers see the old table; if it fails, the old table stays; only on success is it swapped for the new one. Never a half-loaded table.

**Not atomic across tables.** The twelve jobs run one after another, so for a few seconds `openf1_laps` can be new while `openf1_stints` is still old. Nobody sees it: the only reader of `raw` is dbt, which runs *after* `load` in the same job, and the pipeline's `concurrency` group forbids two runs at once. If job 5 fails, tables 1–4 are new and 6–12 old, `load` fails, dbt never runs, and the next run rebuilds all twelve.

#### 2. An explicit list of files, never a wildcard

BigQuery accepts `gs://bucket/raw/laps/*`, which would be one line. We build the list by hand from the manifests instead:

- A wildcard also matches **unmarked** files: a Grand Prix that crashed mid-write would leak half-written data into the warehouse. The marker only protects readers that check it; the loader checks it by building its list from the manifests.
- It only lists endpoints that each manifest names (`if endpoint in m["rows"]`): a Grand Prix ingested before an endpoint existed (e.g. `overtakes`, added later) doesn't make a job point at a missing file, which would fail the whole load.
- Season files (`meetings`, `sessions`) are loaded only for seasons that have at least one marker, and only if the file exists.
- An empty lake **fails** (`no complete meetings to load`) instead of truncating every table to zero rows.

#### 3. The schema comes from the contract, through Parquet

We never declare a BigQuery schema. Parquet is **self-describing**: each file carries its own schema, and BigQuery reads it. That schema is the pyarrow contract from ingestion, so there is one source of truth for types:

| Contract (pyarrow) | Parquet | BigQuery |
|---|---|---|
| `pa.int64()` | INT64 | `INTEGER` |
| `pa.float64()` | DOUBLE | `FLOAT` |
| `pa.string()` | UTF8 string | `STRING` |
| `pa.timestamp("us", tz="UTC")` | TIMESTAMP, adjusted to UTC | `TIMESTAMP` (without `tz` it would land as `DATETIME`, a time with no time zone) |

With `WRITE_TRUNCATE` the table is replaced *including its schema*, so a column added to the contract appears in BigQuery on the next load with no migration. The flip side: a column removed from the contract disappears, and any dbt model using it fails — which is what we want to find out in CI.

#### 4. Code shape: the loader is a function you pass in

```python
Loader = Callable[[str, list[str]], int]  # (table, uris) -> rows loaded


def load(lake: Lake, loader: Loader) -> dict[str, int]: ...
def bigquery_loader(project, dataset="raw", client=None) -> Loader: ...
```

- `load` only decides *what* to load; `bigquery_loader` knows *how*. Tests pass a fake loader that records the calls, so the whole plan is tested without GCP. Porting to Snowflake or Redshift means writing one more loader, not touching the plan.
- `from google.cloud import bigquery` is imported *inside* the function: `pitwall ingest` and the tests never pay for loading the BigQuery library.
- The CLI refuses `load` against a local lake: BigQuery can only read from `gs://`, not from a laptop.

#### 5. Who is allowed to do it

The pipeline service account has three grants ([`infra/gcp/iam.tf`](../infra/gcp/iam.tf)), split on purpose:

| Grant | Scope | Why |
|---|---|---|
| `storage.objectAdmin` | the raw bucket only | read (load) and write (ingest) the lake |
| `bigquery.dataEditor` | each of the five datasets | replace tables' data |
| `bigquery.jobUser` | the project | *run* jobs — a load job is a project resource |

"Allowed to run jobs" and "allowed to touch this data" are separate permissions in BigQuery. A job user without data access can run nothing useful; data access without job user can't run a query. Least privilege means granting each at the smallest scope that works. How that account gets credentials with no key file is block 3.

#### Alternatives rejected

- **Incremental load per Grand Prix** (`raw.openf1_laps$<partition>` with a truncate of only that partition): the right tool when a full reload costs real time or money — telemetry in phase 2 (~500k rows per race). For 11 MB it is more moving parts for no gain.
- **External tables** over the lake (BigQuery reads GCS on every query): no load step at all, but every dbt run re-reads Parquet from GCS (slower, no caching) and the table definition depends on the Hive paths.
- **Streaming inserts / Storage Write API:** built for rows arriving continuously; billed, and pointless for a weekly batch.
- **`bq load` in the Makefile:** fewer lines, but the manifest logic (which files, which endpoints) would move into shell.

#### Where else it applies

- Full refresh vs incremental is the same decision as a dbt `table` vs `incremental` materialization (block 4).
- "Atomic per table, not per dataset" is why multi-table pipelines either run consumers strictly afterwards (us), or use table formats with multi-table transactions, or publish through a swap (write-audit-publish).
- Separating "run jobs" from "access data" is how every cloud warehouse does IAM (Snowflake warehouses vs database grants, Databricks compute vs Unity Catalog).

> **In short.** Every run, BigQuery throws the raw tables away and rebuilds them from the lake — it's small, free and can't create duplicates. Each table is swapped in one go, so nobody ever sees a half-loaded table. The loader only takes the files listed in the "ready" markers, never "everything in the folder", so a half-written Grand Prix can't sneak in. The column types come straight from the Parquet files, which come from the contract: one definition, used end to end.

### Infrastructure (`infra/gcp/`, `Makefile`)

Everything pitwall runs on in GCP exists because of two commands per environment: `make bootstrap` (a GCP project with billing and a budget alert, via `gcloud`, once) and `make apply` (everything *inside* the project, via Terraform). Two identical projects, `pitwall-tr-dev` and `pitwall-tr-prod`. GitHub Actions reaches them **without a single key**, and two guardrails keep the bill at zero.

```
make bootstrap ENV=dev    gcloud: create project in the org → link billing → budget alert (5 EUR)
        │                  (once; needs billing-level permissions, so it lives outside Terraform)
make apply ENV=dev        terraform workspace "dev" → APIs, bucket, 5 datasets, service accounts,
        │                  IAM grants, Workload Identity pool + GitHub provider, query quota
make gh-vars ENV=dev      terraform outputs → GitHub Environment "dev" variables
        │                  (PITWALL_PROJECT, PITWALL_WIF_PROVIDER, PITWALL_SERVICE_ACCOUNT)
workflows                 read those variables and log in through WIF
```

#### 1. Two layers: bootstrap outside Terraform, everything else inside

Creating a project, linking it to a billing account and creating a budget need permissions at **organization and billing-account level**. Giving Terraform those powers would mean its credentials could create projects and spend money anywhere in the org. So that one-off part is a scripted `gcloud` sequence (`make bootstrap`), and Terraform only manages what lives *inside* the project, where a mistake stays contained. The budget is created **before** any resource exists: the alarm is in place before the first thing that could cost money.

#### 2. How Terraform works inside

- **Declarative.** The `.tf` files describe the *desired* end state ("a bucket named X with these settings"), not steps. Terraform works out the steps.
- **State** is Terraform's memory: a JSON file mapping each resource in the code (`google_storage_bucket.raw`) to the real object's ID in GCP. Without it, Terraform can't tell "create" from "already exists".
- **`plan`** = *refresh* (ask the GCP APIs how every resource in state looks today) → *diff* against the code → a list of creates, updates, replacements and deletes. **`apply`** executes that list.
- **Dependency graph.** References between resources (`google_storage_bucket.raw.name` inside the IAM grant) give an order; Terraform walks the graph and runs independent branches in parallel. Where there's no reference but there is a real dependency, we state it: every resource `depends_on` the enabled APIs, because enabling an API isn't instant and the first `apply` would otherwise race and get a 403.
- **Providers** are plugins that translate resources into API calls (`hashicorp/google`, `google-beta` for the quota override, which only exists in beta, and `random`). `~> 7.0` allows any 7.x; the committed [`.terraform.lock.hcl`](../infra/gcp/.terraform.lock.hcl) pins the exact version and its checksums, so everyone gets the same binary.
- **One root, two environments: workspaces.** `make apply ENV=prod` runs `terraform workspace select -or-create prod`: same code, **separate state file** (`terraform.tfstate.d/<env>/`), different variables (`-var env=prod -var project_id=pitwall-tr-prod`). What differs between environments is expressed in code: `count = var.env == "prod" ? 1 : 0` creates the dashboard account only in prod, and the CI dataset permission only in dev.
- **`for_each`** over a list creates one resource per item with a readable address: `google_bigquery_dataset.layers["marts"]`. Adding a sixth dataset is one word in `local.datasets`.
- **`billing_project` + `user_project_override`** make API calls bill and count quota against the project itself, not whatever default project your laptop's `gcloud` has configured.
- **State is local** (git-ignored, on Tomas's laptop). Fine while only one person applies; the day CI applies Terraform, it moves to a remote backend (a GCS bucket with locking), recorded in an ADR.

#### 3. Identity without keys: Workload Identity Federation

The classic way for CI to reach GCP is a service-account JSON key stored as a GitHub secret: a password that never expires, can leak through logs or forks, and must be rotated by hand. pitwall has **no keys anywhere**. Instead, GitHub proves who the job is and GCP trades that proof for a credential that expires in an hour:

```
GitHub Actions job (permissions: id-token: write)
  1. asks GitHub for an OIDC token: a JWT signed by GitHub with claims —
     repository_id, workflow_ref, ref, event_name, environment…
  2. google-github-actions/auth sends it to Google STS (sts.googleapis.com)
        └─ the pool's provider verifies GitHub's signature (issuer
           token.actions.githubusercontent.com), maps claims to attributes and
           evaluates the attribute_condition → false = rejected
  3. STS returns a short-lived federated token
  4. IAM Credentials (iamcredentials.googleapis.com) exchanges it for an access token
     of pitwall-pipeline@…, allowed because the repo principal holds
     roles/iam.workloadIdentityUser on that service account
  5. gcloud, bq, dbt and pyarrow find it through ADC; it expires in ~1 h
```

The `attribute_condition` ([`iam.tf`](../infra/gcp/iam.tf)) is the guest list, clause by clause:

| Clause | Blocks |
|---|---|
| `repository_id == '1396373223'` | every other GitHub repository in the world. Without a condition, *any* repo could exchange tokens here. The numeric ID, not the name: a deleted repo's name can be re-registered by someone else, its ID can't |
| `workflow_ref.startsWith('…/.github/workflows/pitwall-')` | other workflows in the same repo (a future project's CI can't act as pitwall) |
| `event_name != 'pull_request_target'` | a trigger that runs with the base repo's privileges on a PR's context — the classic way forks steal CI secrets |
| prod: `environment == 'prod'` | any job not running in the GitHub Environment `prod` |
| prod: `ref in ['refs/heads/dev', 'refs/heads/main']` | runs triggered from any other branch. `dev` is allowed because the Monday cron always starts on the default branch (`dev`) and *then* checks out `main`; the token carries the triggering ref |

**Defense in depth.** The GitHub Environment `prod` has its own rule: only `dev` and `main` may deploy to it. So prod is guarded twice, by GitHub (who may enter the environment) and by GCP (what the token must say). Either one alone would be a single point of failure.

**Least privilege, also inside the workflows:** only jobs that talk to GCP get `id-token: write`. The jobs that run `npm` (the site build) don't: a malicious npm package there can't mint a GCP token. Fork PRs can't mint tokens at all, so their cloud jobs are skipped.

**Accepted trade-off:** in dev, any `pitwall-*` workflow from any branch of this repo can act as the dev pipeline account, so anyone with write access to the repo can reach dev. Prod is the environment that needs the stricter rules.

#### 4. Two projects, and the accounts inside them

| | dev | prod |
|---|---|---|
| Used by | the laptop (`gcloud` user), CI on every PR, manual runs | the Monday cron and releases, code from `main` only |
| `pitwall-pipeline` SA | lake + 5 datasets + jobs, **plus** `bigquery.user` to create/drop per-PR CI datasets | lake + 5 datasets + jobs |
| `pitwall-dashboard` SA | — | read-only on `marts` + jobs: what `site-export` runs as |
| WIF condition | repo + pitwall workflows + no `pull_request_target` | the same + environment `prod` + branch `dev`/`main` |

Separate projects, not prefixes in one project, because a project is GCP's isolation boundary: its own IAM, quotas, billing lines and blast radius. A broken dev can't touch prod, and deleting dev is one command.

#### 5. Cost guardrails: one warns, the other stops

- **Budget alert** (bootstrap): emails at 50 / 90 / 100 % of 5 EUR. It must be in the billing account's currency (EUR here). It **only warns**, after the money is spent, and it can lag by hours.
- **BigQuery query quota** (Terraform, `google-beta`): at most **50 GiB scanned per day** per project, against a default of 200 TiB (about 1,250 USD a day at the on-demand list price of 6.25 USD/TiB). It **stops**: the query that crosses the line fails. Our dbt build scans megabytes, so the quota never bites in normal operation; it exists for the `select *` in a loop.
- **Region `us-central1`:** inside GCS's free-tier regions, and bucket and datasets in the same region (loads from GCS require compatible locations).
- **GCS soft delete off** (`retention_duration_seconds = 0`): by default GCS keeps every overwritten or deleted object for 7 days and bills it. Every ingestion overwrites Parquet files, so soft delete would quietly accumulate copies.
- **Expected bill: 0/month.** Tens of MB of storage, free loads, tiny queries, and GitHub Actions and Pages are free for public repos.

#### 6. Teardown is part of the design

`make destroy ENV=dev` deletes everything Terraform created, data included ([ADR 0005](decisions/0005-regenerable-storage-is-force-destroyed.md)):
- `force_destroy` on the bucket and `delete_contents_on_destroy` on the datasets: GCS and BigQuery refuse to delete non-empty containers by default. This is **only** acceptable because the data is regenerable from OpenF1 (~1 h backfill); on irreplaceable data it would be a loaded gun.
- `disable_on_destroy = false` on APIs: turning an API off can break things outside Terraform; leaving it on costs nothing.
- The WIF pool ID gets a `random_id` suffix: a deleted pool stays reserved for 30 days, so without it `destroy` → `apply` would fail for a month. Consequence: the provider name changes, so `make gh-vars` must be re-run after an apply that recreates it.
- The destroy → apply cycle was actually run on dev before prod was left running: infrastructure you have never rebuilt is infrastructure you *hope* is reproducible.

#### Alternatives rejected

- **Service-account JSON keys** as GitHub secrets: the default in most tutorials; also blocked in this organization, whose policy forbids creating service-account keys (the same policy that ruled out Evidence's key-only BigQuery connector, ADR 0007). WIF is strictly better whenever the CI provider speaks OIDC.
- **One project with `dev_`/`prod_` prefixes:** fewer moving parts, but shared IAM, quotas and blast radius ([ADR 0003](decisions/0003-gcp-two-projects-bigquery-only.md)).
- **Terraform creating the projects:** needs org/billing admin credentials in Terraform; not worth it for two projects.
- **Remote state from day one:** a bucket, locking and bootstrap-of-the-bootstrap for a single operator. Deferred until CI applies.
- **Pulumi / OpenTofu:** Pulumi uses real programming languages; OpenTofu is the open-source fork of Terraform. Terraform chosen for market share (lab rule: industry standard over niche).

#### Where else it applies

- OIDC token exchange is how every modern CI reaches every cloud: AWS (`AssumeRoleWithWebIdentity`), Azure (federated credentials), Kubernetes pods (GKE Workload Identity, EKS IRSA), even PyPI's trusted publishing.
- "Budgets warn, quotas stop" applies to any metered service: API spend limits, Snowflake resource monitors, Databricks cluster policies.
- "Bootstrap outside, everything else inside IaC" is the standard landing-zone split: a platform team creates accounts/projects; product teams' Terraform lives inside them.

> **In short.** A one-off script creates each GCP project with its budget alarm; Terraform builds everything inside it from code and can tear it all down and rebuild it. GitHub never holds a password for GCP: each run shows a signed ID card from GitHub, GCP checks it against a strict guest list (this repo, these workflows, and for prod only the prod environment on dev/main) and hands out a key that expires in an hour. Two brakes keep it free: a budget that emails when money is spent, and a daily query limit that simply refuses to spend more.

### Transformation I: dbt project, staging and intermediate (`transform/`)

dbt turns a folder of `select` statements into a tested pipeline inside BigQuery. pitwall's models flow in three layers: **staging** cleans each raw table one to one, **intermediate** applies the racing rules (when was the Safety Car out? which tyre was each lap on? what position was the car in?), and **marts** answer questions (next block). This block covers the project setup and the first two layers.

```
raw.openf1_* (12 tables, from load)
   │  sources.yml: declares them + source tests
staging.stg_openf1__* (10 views)        one per raw table: dedupe, rename, type, no logic
   │
intermediate.int_neutralised_laps (view)    race-control messages → laps under SC / VSC / red flag
intermediate.int_laps_enriched (view)       every lap + tyre + pit flags + neutralisation
   │                                        + position at the end of the lap + is_clean_lap
marts.* (tables, next block)
```

#### 1. How dbt works inside

- **A model is a `select`.** dbt wraps it in DDL according to its *materialization*: `view` → `create or replace view … as <select>`; `table` → `create or replace table … as <select>`. You never write `create` or `insert`.
- **`ref()` and `source()` build the graph.** `{{ ref('stg_openf1__laps') }}` does two things: it compiles to the full table name (`pitwall-tr-dev.staging.stg_openf1__laps`), and it records an edge "this model depends on that one". From all the edges dbt builds a DAG and runs models in dependency order, up to `threads: 4` at once.
- **Compile, then execute.** dbt renders Jinja (`{{ }}`, `{% %}`) into plain SQL (visible in `target/compiled/`), then sends each statement to BigQuery as a query job. dbt itself moves no data: all the work happens in the warehouse.
- **`dbt build`** runs, in DAG order, for each node: unit tests → the model → its data tests. If a test with severity `error` fails, everything downstream of it is **skipped**: a broken staging model never feeds the marts, and the dashboard keeps its last good version.

#### 2. Project configuration

- **Materializations by layer** ([`dbt_project.yml`](../transform/dbt_project.yml)): staging and intermediate are **views**, marts are **tables**. A view stores nothing and is always current, but is recomputed every time it is read; a table is computed once per build and read many times. Marts are what `site-export` reads, so they are tables; the layers in between are read once per build by the next layer, so views cost nothing extra and never go stale.
- **One dataset per layer** with [`generate_schema_name`](../transform/macros/generate_schema_name.sql). dbt's default would name the dataset `<target schema>_<custom schema>` (e.g. `staging_marts`). The override gives clean names in dev/prod (`staging`, `intermediate`, `marts`, `audit`, all created by Terraform), and in CI prefixes every layer with the per-PR name (`ci_pr_12_marts`), so the same code builds an isolated copy per PR.
- **Profile** ([`profiles.yml.example`](../transform/profiles.yml.example)): `method: oauth` means "use ADC" — your `gcloud` login on the laptop, the WIF token in Actions; no key file. `maximum_bytes_billed: 1000000000` makes BigQuery reject any single query that would bill more than 1 GB, *before* running it: a third cost guard, after the budget and the daily quota, at query level. `job_execution_timeout_seconds: 300` kills a runaway query.
- **Sources** ([`sources.yml`](../transform/models/sources.yml)) declare the raw tables (project from `PITWALL_BQ_PROJECT`, dataset `raw`) and carry **source tests**: data quality checked at the door, before any model reads it (details in block 5).
- **Tests store their failures** (`+store_failures: true`, `+schema: audit`): every failing row of every test lands in a table in `audit`, so a failure is something you can query, not just a red line in a log.
- **Doc blocks** ([`docs.md`](../transform/models/docs.md)): a shared column (`session_key`, `compound`, `neutralisation`) is explained once in plain language and reused everywhere with `{{ doc('…') }}`. Every model's description starts with its grain.

#### 3. Staging: one model per raw table, no business logic

Every staging model has the same shape ([example](../transform/models/staging/stg_openf1__laps.sql)):

```sql
-- grain: one row per lap of one driver in one session
with source as (
    select * from {{ source('openf1', 'openf1_laps') }}
),

deduplicated as (
    select * from source
    where true                       -- BigQuery only allows QUALIFY next to WHERE/GROUP BY/HAVING
    qualify row_number() over (
        partition by session_key, driver_number, lap_number   -- the natural key = the grain
        order by _ingested_at desc                            -- latest download wins
    ) = 1
)

select
    session_key, meeting_key, driver_number, lap_number,
    date_start as started_at,          -- names say what they are
    lap_duration as lap_time_s,        -- and their unit
    ...
    coalesce(is_pit_out_lap, false) as is_pit_out_lap   -- null booleans become false
from deduplicated
```

- **Deduplicate on the natural key.** Ingestion is idempotent, so why dedupe? Because staging must *guarantee* its grain whatever the source does. It isn't theoretical: in dev, `raw.openf1_race_control` has 10,289 rows and staging 10,281 — OpenF1 itself sends the same message twice. `QUALIFY` filters on a window function's result, the way `HAVING` filters on an aggregate; `row_number() … = 1` keeps exactly one row per key.
- **Rename for meaning and units:** `date` → `recorded_at`, `lap_duration` → `lap_time_s`, `position` → `finish_position` / `grid_position`. A column name that carries its unit prevents the classic seconds-vs-milliseconds bug.
- **Normalise, don't interpret:** `upper(compound)` with `UNKNOWN` for nulls; `'#' || team_colour` so the site can use it directly; `coalesce(lane_duration, pit_duration)` takes the pit-lane time from whichever field is filled (both are, today; the fallback is defensive).
- **Flag known defects instead of dropping them:** stints whose `lap_start > lap_end` (a source defect) are kept with `has_valid_lap_range = false`; the mart decides to exclude them. Staging never throws data away silently.
- **Rename to prevent wrong joins:** the starting grid is attached by OpenF1 to the *qualifying* session that set it, so staging renames its key to `qualifying_session_key`. A careless `join … using (session_key)` with a race simply can't happen.
- **Only what is used:** `weather` and `overtakes` stay as sources without staging models until a page needs them, and columns OpenF1 never fills are not carried over.

#### 4. `int_neutralised_laps`: from messages to laps under Safety Car

**The problem.** Race control doesn't publish "laps 2–5 were under Safety Car". It publishes **events**: "SAFETY CAR DEPLOYED" on lap 2, "SAFETY CAR IN THIS LAP" on lap 5. We need **one row per lap** that was neutralised, because laps under SC/VSC say nothing about tyre wear (everyone drives slowly) and make pit stops cheaper. A real example from dev, the 2025 São Paulo Grand Prix:

| Lap | Message | → Result |
|---|---|---|
| 2 | SAFETY CAR DEPLOYED | laps 2, 3, 4, 5 = `SC` |
| 5 | SAFETY CAR IN THIS LAP | |
| 7 | VIRTUAL SAFETY CAR DEPLOYED | laps 7, 8 = `VSC` |
| 8 | VIRTUAL SAFETY CAR ENDING | |

**How the SQL does it** ([model](../transform/models/intermediate/int_neutralised_laps.sql)), CTE by CTE:
1. `messages` — keep SafetyCar messages and red flags; classify each as a *start* (`SC`/`VSC` deployed), an *end* (SC in this lap / VSC ending) or a red flag.
2. `starts`, `ends` — split them.
3. `interruptions` + `next_interruption` — for each start, the **first** thing after it that interrupts a period: a red flag or a new deployment (`qualify row_number() … order by interruptions.recorded_at) = 1` picks "the next one").
4. `periods` — each start's last lap is, in order of preference (`coalesce`): the first matching end message *before* the next interruption; otherwise the interruption (a red-flag lap still counts, a new deployment's lap belongs to the new period); otherwise the session's last lap.
5. `period_laps` — expand each interval into one row per lap: `cross join unnest(generate_array(first_lap, last_lap))` turns `(2, 5)` into 2, 3, 4, 5.
6. Add every red-flag lap as `RED`, and `union distinct`.

**Why the edge rules exist** — each one is a real race and a unit test in [`_intermediate.yml`](../transform/models/intermediate/_intermediate.yml):
- A period with **no end message** (it happens) would otherwise run to the end of the race and mark 20 green laps as neutralised. It stops before the next deployment, or at the last lap.
- A **VSC upgraded to a full SC** has no "VSC ENDING": the VSC stops the lap before the SC starts.
- **Brazil Sprint 2025:** SC, then a red flag, then a standing restart with no "SC in" message. The red flag closes the SC period.

This shape — pair start/end events into intervals, then expand intervals into rows of the grain you need — is the same as building user sessions from clicks, machine downtime from status events, or SLA windows from tickets.

#### 5. `int_laps_enriched`: every lap with its full context

The model everything downstream reads ([model](../transform/models/intermediate/int_laps_enriched.sql)). Grain: one lap of one driver in one session. Each lap gets:

- **Its tyres** — join to the stint whose range contains the lap (`lap_number between first_lap and last_lap`). `tyre_age_laps = tyre_age_at_start + (lap_number − first_lap)`: a set can start used (from qualifying), so age doesn't start at 0. If the source has overlapping stints, the `qualify` keeps the later one so a lap is never duplicated (a fan-out join, caught by the grain test).
- **Pit flags** — `is_pit_in_lap` if the pit table has that lap (the driver entered the pits at the end of it); `is_pit_out_lap` from the source (the lap started in the pit lane).
- **Neutralisation** — one value per lap even when several apply: `RED` outranks `SC`, which outranks `VSC`.
- **Position at the end of the lap: an as-of join.** `position` is not one row per lap: it's a row *each time a car's position changes*. To know the position at the end of lap 12, take **the latest change recorded at or before the moment lap 12 ended**:

  ```sql
  inner join positions
      on positions.driver_number = timed.driver_number
      and positions.recorded_at <= timed.ended_at          -- everything up to that moment
  qualify row_number() over (
      partition by timed.session_key, timed.driver_number, timed.lap_number
      order by positions.recorded_at desc                 -- the most recent of those
  ) = 1
  ```

  `ended_at` is `started_at + lap_time_s`, or the next lap's start when the time is missing (`lead()`). This "value as of a moment" join is one of the most useful patterns in data engineering (prices at trade time, a customer's plan at invoice time, features at prediction time).
- **`is_clean_lap`** — whether the lap says something about tyre wear. Each condition removes a known distortion:

  | Condition | Removes |
  |---|---|
  | `lap_number > 1` | the standing start (slow, chaotic) |
  | `lap_time_s is not null` | timing gaps |
  | `not is_pit_in_lap and not is_pit_out_lap` | laps that include driving through the pit lane |
  | `neutralisation is null` | Safety Car / VSC / red-flag laps |
  | `lap_time_s <= 1.2 × session median` | damage, traffic chaos, laps around a red flag |

  The median (`percentile_cont(…, 0.5) over (partition by session_key)`) rather than the mean, because the slow laps it's meant to catch would drag a mean up. In dev, 88,872 of 103,549 laps (86 %) are clean.

#### 6. Unit tests: pinning the racing rules

dbt **unit tests** (YAML, dbt ≥ 1.8) feed a model hand-made input rows instead of real tables and compare the output with expected rows. dbt replaces each `ref()` with a CTE of literal values, so the test runs in BigQuery but reads no data. pitwall has four for the intermediate layer, each a race situation written as data: SC + VSC pairing, a period without an end, red flag and VSC→SC, and a six-lap stint covering tyre age, in/out laps, VSC, a damage lap and positions. Real data can't test this: next season may have no VSC-to-SC upgrade at all, and the rule must still be right when one happens.

#### Alternatives rejected

- **Logic in Python** (pandas in the extractor): it would run outside the warehouse, untested by dbt, and every rule change would mean re-ingesting.
- **One big query per mart:** no reuse; `int_laps_enriched` feeds four marts.
- **Intermediate as tables:** faster to read, but storage and a rebuild step for something only the next layer reads.
- **SQLMesh** (column-level lineage, virtual environments): technically strong, but dbt is the market standard (lab rule).

> **In short.** dbt runs our SQL files in the right order inside BigQuery and tests them on every build. Staging just cleans each raw table: one row per thing, clear names with units, no duplicates, nothing interpreted. The intermediate layer holds the racing rules: it turns "Safety Car deployed / in this lap" messages into a list of slow laps, and gives every lap its tyre, its age, its pit flags, its position at the moment it ended, and a verdict on whether it's a "clean" lap worth using to measure tyre wear. The tricky rules are pinned with small hand-made test races, so they stay right even in seasons when those situations never happen.

## Local vs production

| | Laptop | Cloud (dev / prod) |
|---|---|---|
| Lake | `PITWALL_LAKE_URI=.lake` (local folder) | `gs://pitwall-tr-<env>-raw` |
| Identity | your `gcloud` user credentials (ADC: `gcloud auth application-default login`) | `pitwall-pipeline` service account through WIF, a token that lasts ~1 h |
| Environment choice | `ENV=dev` (default) or `ENV=prod` on any `make` target | the workflow's GitHub Environment (`dev` / `prod`) and its variables |
| Terraform | only from the laptop; local state per workspace | CI runs `terraform fmt` and `validate`, never `apply` |
| dbt | `make transform` → `dbt build --target dev`, your ADC | same command with `--target prod` (pipeline) or `--target ci` (per-PR datasets) |
| `pitwall load` | refused on a local lake (BigQuery reads only `gs://`) | 12 load jobs into `<project>.raw`, seconds each |

## Where it breaks

| Symptom | Cause | Fix |
|---|---|---|
| `--latest` run fails with "still have no laps/stints 3 days after the race" | OpenF1 never published that race's data | Check the API by hand; re-run `--meeting <key>` once it appears |
| A meeting's files exist in the lake but it never reaches BigQuery | Crash between the first write and the marker | Nothing to clean: the next run overwrites it; the loader ignores unmarked meetings |
| Warning "dropping columns not in the contract" | OpenF1 added a field | Decide whether we want it; add it to `CONTRACTS` by PR |
| Run crashes in `time.sleep` with "Invalid value NaN" or a negative value | A `Retry-After` header that is negative or `nan` is passed through unclamped | Clamp the delay to `[0, MAX_DELAY]` in `backoff_delay` |
| `load` fails with "the lake has no complete meetings to load" | No markers in the lake (wrong `PITWALL_LAKE_URI`/env, or a fresh environment) | Check `gcloud storage ls gs://pitwall-tr-<env>-raw/raw/_success/`; ingest first |
| `load` fails on one table; some raw tables are new, others old | A load job failed midway through the twelve | Nothing downstream ran (dbt comes after); fix the cause and re-run `load` — it rebuilds everything |
| A dbt model fails after a load with "Unrecognized name" | A column was removed from the contract; `WRITE_TRUNCATE` replaced the table schema | Intended: restore the column or update the model, in the same PR |
| First `make apply` in a new project fails with 403 "API has not been used… or it is disabled" | Enabling an API takes a minute to propagate | Re-run `make apply`; `depends_on` covers ordering, not propagation |
| Workflow fails at `auth` with "rejected by the attribute condition" | The token's claims don't match: workflow not named `pitwall-*`, a prod run from another branch, or not in the `prod` environment | Compare the job's trigger/branch/environment with `attribute_condition` in `iam.tf` |
| Workflow fails at `auth` after a destroy → apply | The WIF pool got a new random suffix; GitHub still holds the old provider name | `make gh-vars ENV=<env>` |
| Terraform wants to create resources that already exist | The local state is lost or a different workspace is selected | `terraform workspace show`; if lost, `terraform import` or destroy the project and re-apply (the data is regenerable) |
| Budget creation fails in bootstrap | The budget currency differs from the billing account's (EUR) | Use the account's currency: `BUDGET_AMOUNT` is in EUR |
| A mart test fails with duplicate keys after a source change | A fan-out join: a lap matched two stints (overlapping ranges) or two positions | Query the failing rows in `audit`; fix the join's `qualify`/condition, not the test |
| Green laps show as `SC` for the rest of a race | A Safety Car period without an end message ran on | Check `stg_openf1__race_control` for that session; add the case to the unit tests in `_intermediate.yml` |
| `dbt build` skips every mart | An upstream `error` test failed; dbt skips downstream nodes | `dbt build` output → first failure; `audit.<test name>` holds the rows |
