# pitwall — How it works

The walkthrough: read this after the [README](../README.md) to understand the insides. Written during the tutor reviews, so every section explains *why*, not only *what*.

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

**Unit of work = one Grand Prix (a *meeting*).** Every selector reduces to "ingest these meetings": `--meeting 1255` is one, `--season 2024` is all finished meetings of a year, `--latest` is finished meetings with no success marker yet. One code path means the backfill and the Monday run cannot drift apart.

**The client ([`client.py`](../src/pitwall/client.py))** prevents before it reacts:
- `RateLimiter` enforces 2.1 s between requests (30/min with a margin). It measures with `time.monotonic`, which never jumps when the wall clock is adjusted.
- Retries only what is transient (429, 5xx, network errors), with `2^attempt + random()` seconds of backoff, capped at 60 s, honouring `Retry-After`. Other 4xx mean our request is wrong, so they fail at once.
- OpenF1 answers "no data" with **HTTP 404** and body `{"detail": "No results found."}`. Only that exact body becomes `[]`; any other 404 fails.
- `clock` and `sleep` are constructor parameters, so tests run the limiter and backoff without waiting.

**The contract ([`contracts.py`](../src/pitwall/contracts.py))** is the boundary between an API we don't control and our lake. One explicit `pyarrow` schema per endpoint:
- a required field missing or null → `ContractError`, the run fails;
- an unknown new field → warning, dropped until added by PR (schema evolution is a reviewed decision, not an accident);
- every value is cast to its declared type; `1.0` is accepted as an int, `1.5` is not; booleans are never silently turned into ints (in Python `True` *is* an `int`, hence the explicit check).
- Each row is stamped with `_ingested_at`.
- `level` says how an endpoint is fetched: by `year` (meetings, sessions), by `meeting_key` (starting grid, attached to qualifying) or by `session_key` (everything else).

**The use cases ([`ingest.py`](../src/pitwall/ingest.py)):**
- `refresh_season` rewrites `meetings` and `sessions` for the year — but never with an empty answer, because the loader reloads season files in full and one flaky "no results" would wipe the season from the warehouse.
- `finished_meetings` only picks meetings whose last Race/Sprint ended **6 h** ago (`SETTLE_TIME`): OpenF1 needs time to publish.
- `ingest_meeting` fetches *everything* into memory and validates it first, then: delete old marker → write every Parquet file → write the marker last. If `laps` or `stints` are still empty it returns `False` without touching the lake; the next run retries.
- `ingest_latest` also scans the previous season for 45 days (a December race is not lost at New Year) and **fails loudly** if a meeting is still empty 3 days after the race, after ingesting the rest — silence forever is worse than a red run.

**The lake ([`lake.py`](../src/pitwall/lake.py))** hides local vs GCS behind `pyarrow.fs`: the rest of the code only sees relative paths such as `raw/laps/season=2025/meeting_key=1255/part.parquet`.
- Hive-style `key=value` folders make partitions readable by any engine, but `read_table` opens a file handle so pyarrow does *not* add `season` / `meeting_key` as columns.
- Directories are created only on local disk: object stores have none, and `create_dir` on GCS can create buckets.
- **The lake is the state.** Which meetings are done = which markers exist. No database of "last run".

**Why a custom extractor and a lake** ([ADR 0002](decisions/0002-lake-first-custom-extractor.md)): dlt would do this in fewer lines but hides the mechanics this project exists to teach; writing straight into BigQuery would lose the replay (every model change would re-hit the API) and tie extraction to one warehouse.

## Local vs production

| | Laptop | Cloud (dev / prod) |
|---|---|---|
| Lake | `PITWALL_LAKE_URI=.lake` (local folder) | `gs://pitwall-tr-<env>-raw` |
| Identity | your `gcloud` user credentials (ADC) | *(block 3)* |

## Where it breaks

| Symptom | Cause | Fix |
|---|---|---|
| `--latest` run fails with "still have no laps/stints 3 days after the race" | OpenF1 never published that race's data | Check the API by hand; re-run `--meeting <key>` once it appears |
| A meeting's files exist in the lake but it never reaches BigQuery | Crash between the first write and the marker | Nothing to clean: the next run overwrites it; the loader ignores unmarked meetings |
| Warning "dropping columns not in the contract" | OpenF1 added a field | Decide whether we want it; add it to `CONTRACTS` by PR |
| Run crashes in `time.sleep` with "Invalid value NaN" or a negative value | A `Retry-After` header that is negative or `nan` is passed through unclamped | Clamp the delay to `[0, MAX_DELAY]` in `backoff_delay` |
