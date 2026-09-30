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

## Local vs production

| | Laptop | Cloud (dev / prod) |
|---|---|---|
| Lake | `PITWALL_LAKE_URI=.lake` (local folder) | `gs://pitwall-tr-<env>-raw` |
| Identity | your `gcloud` user credentials (ADC) | *(block 3)* |
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
