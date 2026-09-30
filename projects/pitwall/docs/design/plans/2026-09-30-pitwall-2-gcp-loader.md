# pitwall — Plan 2: GCP infrastructure + BigQuery loader

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The dev environment exists in GCP (bucket, datasets, least-privilege service accounts, Workload Identity Federation, BigQuery quota), the 2025 season sits in the GCS lake, `pitwall load` rebuilds BigQuery raw tables from it, and `make destroy` / `make apply` have been cycled successfully.

**Architecture:** A one-off `make bootstrap` (gcloud) creates the project, links billing and sets the budget alert. One Terraform root (`infra/gcp/`, workspace per env) owns everything inside the project. The lake gains GCS-safe writes and an explicit URI/manifest API; a new `load` module turns success markers into one `WRITE_TRUNCATE` load job per raw table, behind an injectable loader so the logic is unit-tested without BigQuery.

**Tech Stack:** Terraform ≥ 1.9 (providers `google`, `google-beta`, `random`), gcloud, Python (`google-cloud-bigquery`, pyarrow `GcsFileSystem`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-pitwall-design.md` (§5, §9, §10). Plan 1: `docs/superpowers/plans/2026-09-29-pitwall-1-extractor.md`.

## Global Constraints

- Nothing billable is created before Tomas confirms the expected cost (US$0/month) in chat — Task 5, Step 1 is a hard stop.
- Budget alert (US$5; 50/90/100 %) exists before `terraform apply`.
- Region `us-central1` for the bucket and every dataset.
- Project IDs: `$(PROJECT_PREFIX)-$(ENV)`, default prefix `pitwall-tr` (`pitwall-tr-dev`, `pitwall-tr-prod`). The billing account ID is passed as `BILLING_ACCOUNT=...` and never committed.
- No service-account keys. GitHub reaches GCP only through WIF, conditioned on repository ID `1396373223` (`TomasRipsky/data-engineering-lab`); prod additionally requires GitHub environment `prod`.
- Terraform state: local, one workspace per env (`terraform.tfstate.d/` is git-ignored by `*.tfstate`). `.terraform.lock.hcl` is committed. No `*.tfvars` files (the lab ignores them): variables come from the Makefile.
- Only dev is created in this plan. Prod is bootstrapped in Plan 4 when the pipeline needs it.
- Python rules from Plan 1 still apply (uv, ruff 100 cols, TDD, `httpx.MockTransport`-style fakes instead of mocking libraries).

## Review Focus

1. **A typo in `PITWALL_LAKE_URI` (`gs://pitwal-tr-dev-raw`)** must fail with "bucket not found", never create a bucket → the lake never calls `create_dir` on object stores; test in Task 1.
2. **OpenF1 answering "No results" for `sessions?year=2025` on a flaky day** must not replace a good season file with an empty one (the loader reloads season files in full) → test in Task 1.
3. **A meeting whose manifest predates a new endpoint** must not make the load job reference a file that does not exist → the load plan only uses endpoints listed in each manifest; test in Task 2.
4. **`pitwall load` pointed at a local lake** (BigQuery cannot read laptop files) must fail with a clear message, not a cryptic API error → test in Task 2.
5. **A second `make apply` after `make destroy`** must succeed despite WIF pools being reserved for 30 days after deletion → random pool suffix; verified by the real cycle in Task 5.

---

### Task 1: Lake hardening for GCS

**Files:**
- Modify: `projects/pitwall/src/pitwall/lake.py`
- Modify: `projects/pitwall/src/pitwall/ingest.py` (`refresh_season`)
- Test: `projects/pitwall/tests/test_lake.py`, `projects/pitwall/tests/test_ingest.py`

**Interfaces:**
- Produces: `Lake.uri_of(rel: str) -> str` (`gs://bucket/rel` or an absolute local path), `Lake.is_local: bool`, `Lake.manifests() -> list[dict]` (every success-marker JSON), unchanged `markers()`.
- `refresh_season` keeps the previous season file when the API returns no rows.

- [ ] **Step 1: Branch and failing tests**

```bash
cd "/Users/tomasripsky/Data Engineering/Claude Code Enviroment"
git switch dev && git pull --ff-only
URL=$(gh issue create --title "feat(pitwall): GCP infrastructure and BigQuery loader" \
  --label "type:feat,project:pitwall" \
  --body "Plan 2 of pitwall: docs/superpowers/plans/2026-09-30-pitwall-2-gcp-loader.md")
git switch -c "feat/${URL##*/}-pitwall-gcp-loader"
```

Append to `projects/pitwall/tests/test_lake.py`:

```python
def test_object_store_writes_never_create_directories(monkeypatch):
    # On GCS, pyarrow's create_dir on a missing bucket would create the bucket.
    lake = Lake("gs://some-bucket")
    written = {}

    class NoDirs:
        def create_dir(self, path, recursive=False):
            raise AssertionError(f"create_dir called for {path}")

        def open_output_stream(self, path):
            import io

            class Sink(io.BytesIO):
                def close(self):
                    written[path] = self.getvalue()
                    super().close()

            return Sink()

    monkeypatch.setattr(lake, "_fs", NoDirs())
    lake.write_json(marker_file(2025, 1255), {"meeting_key": 1255})
    assert list(written) == [
        "some-bucket/raw/_success/season=2025/meeting_key=1255.json"
    ]


def test_uri_of_points_at_the_object(tmp_path):
    assert Lake("gs://pitwall-tr-dev-raw").uri_of("raw/laps/x.parquet") == (
        "gs://pitwall-tr-dev-raw/raw/laps/x.parquet"
    )
    local = Lake(str(tmp_path / "lake"))
    assert local.is_local
    assert local.uri_of("raw/a.parquet") == f"{tmp_path / 'lake'}/raw/a.parquet"


def test_manifests_returns_every_marker(lake):
    lake.write_json(marker_file(2024, 1229), {"meeting_key": 1229, "season": 2024})
    lake.write_json(marker_file(2025, 1255), {"meeting_key": 1255, "season": 2025})
    keys = sorted(m["meeting_key"] for m in lake.manifests())
    assert keys == [1229, 1255]
```

Append to `projects/pitwall/tests/test_ingest.py`:

```python
def test_empty_season_response_keeps_the_previous_season_file(
    fixture_client, make_client, lake
):
    ingest_one(fixture_client, lake, 1255, NOW)
    before = lake.read_table(season_file("sessions", 2025)).num_rows

    def empty(request):
        return httpx.Response(404, json=NO_RESULTS)

    ingest_season(make_client(empty), lake, 2025, NOW)
    assert lake.read_table(season_file("sessions", 2025)).num_rows == before > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd projects/pitwall && uv run pytest tests/test_lake.py tests/test_ingest.py -q`
Expected: 4 failures — `create_dir called for …`, `AttributeError: 'Lake' object has no attribute 'uri_of'`, `… 'manifests'`, and the season-file row count `0 == N`.

- [ ] **Step 3: Implement**

In `projects/pitwall/src/pitwall/lake.py`, replace `__init__` and `_prepare` and add the new members:

```python
class Lake:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self._fs, self._root = _resolve(uri.rstrip("/"))
        self.is_local = isinstance(self._fs, fs.LocalFileSystem)

    def _path(self, rel: str) -> str:
        return f"{self._root}/{rel}"

    def _prepare(self, rel: str) -> str:
        path = self._path(rel)
        if (
            self.is_local
        ):  # object stores have no directories; create_dir can create buckets
            self._fs.create_dir(path.rsplit("/", 1)[0], recursive=True)
        return path

    def uri_of(self, rel: str) -> str:
        """Address of `rel` for other systems (e.g. BigQuery load jobs)."""
        return self._path(rel) if self.is_local else f"gs://{self._path(rel)}"
```

and, after `markers()`:

```python
def manifests(self) -> list[dict[str, Any]]:
    """Contents of every success marker: the meetings downstream steps may read."""
    selector = fs.FileSelector(
        self._path(MARKERS_DIR), recursive=True, allow_not_found=True
    )
    root = f"{self._root}/"
    return [
        self.read_json(info.path.removeprefix(root))
        for info in self._fs.get_file_info(selector)
        if info.type == fs.FileType.File and info.base_name.endswith(".json")
    ]
```

In `projects/pitwall/src/pitwall/ingest.py`, replace the body of `refresh_season`:

```python
def refresh_season(
    client: OpenF1Client, lake: Lake, year: int, now: datetime
) -> Season:
    """Fetch and store the season-level files (meetings, sessions).

    An empty answer never replaces a stored file: the loader reloads season files in full, so
    one flaky "No results" would otherwise wipe every session from the warehouse.
    """
    rows = {
        endpoint: client.get(endpoint, year=year)
        for endpoint in ("meetings", "sessions")
    }
    for endpoint, records in rows.items():
        if records:
            lake.write_table(
                season_file(endpoint, year), to_table(endpoint, records, now)
            )
        else:
            log.warning(
                "%s for %s: no rows from OpenF1; stored file left untouched",
                endpoint,
                year,
            )
    return Season(year, rows["meetings"], rows["sessions"])
```

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q && uv run ruff check --fix . && uv run ruff format .`
Expected: 48 passed; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/pitwall/lake.py src/pitwall/ingest.py tests/test_lake.py tests/test_ingest.py
git commit -m "fix(pitwall): make the lake safe for GCS and keep season files on empty answers"
```

---

### Task 2: BigQuery loader and `pitwall load`

**Files:**
- Create: `projects/pitwall/src/pitwall/load.py`
- Modify: `projects/pitwall/src/pitwall/cli.py`
- Test: `projects/pitwall/tests/test_load.py`, `projects/pitwall/tests/test_cli.py`

**Interfaces:**
- Consumes: `Lake.manifests`, `Lake.exists`, `Lake.uri_of`, `Lake.is_local` (Task 1); `CONTRACTS`, `season_file`, `meeting_file` (Plan 1).
- Produces:
  - `RAW_DATASET = "raw"`
  - `load_plan(lake: Lake) -> dict[str, list[str]]` — raw table name (`openf1_<endpoint>`) → URIs
  - `load(lake: Lake, loader: Callable[[str, list[str]], int]) -> dict[str, int]` — table → rows loaded
  - `bigquery_loader(project: str, dataset: str = RAW_DATASET, client=None) -> Callable[[str, list[str]], int]`
  - CLI: `pitwall load` (needs `PITWALL_LAKE_URI` = `gs://…` and `PITWALL_BQ_PROJECT`)

- [ ] **Step 1: Add the dependency**

Run: `uv add google-cloud-bigquery`
Expected: `pyproject.toml` gains `google-cloud-bigquery>=…`.

- [ ] **Step 2: Write the failing tests**

`projects/pitwall/tests/test_load.py`:

```python
from datetime import UTC, datetime

import pytest

from pitwall.ingest import ingest_one
from pitwall.lake import Lake, marker_file
from pitwall.load import RAW_DATASET, bigquery_loader, load, load_plan

NOW = datetime(2025, 4, 1, tzinfo=UTC)


@pytest.fixture
def lake(tmp_path):
    return Lake(str(tmp_path / "lake"))


def test_plan_covers_every_endpoint_from_marked_meetings_only(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    plan = load_plan(lake)
    assert set(plan) == {
        "openf1_meetings",
        "openf1_sessions",
        "openf1_drivers",
        "openf1_laps",
        "openf1_stints",
        "openf1_pit",
        "openf1_position",
        "openf1_weather",
        "openf1_race_control",
        "openf1_session_result",
        "openf1_overtakes",
        "openf1_starting_grid",
    }
    assert plan["openf1_laps"] == [
        lake.uri_of("raw/laps/season=2025/meeting_key=1255/part.parquet")
    ]
    assert plan["openf1_sessions"] == [
        lake.uri_of("raw/sessions/season=2025/part.parquet")
    ]


def test_plan_ignores_unmarked_meetings(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    lake.delete(marker_file(2025, 1255))  # e.g. a crashed re-ingestion
    assert all(uris == [] for uris in load_plan(lake).values())


def test_plan_only_uses_endpoints_listed_in_each_manifest(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    manifest = lake.read_json(marker_file(2025, 1255))
    del manifest["rows"]["overtakes"]  # a meeting ingested before overtakes existed
    lake.write_json(marker_file(2025, 1255), manifest)
    assert load_plan(lake)["openf1_overtakes"] == []


def test_load_calls_the_loader_per_table_with_uris(fixture_client, lake):
    ingest_one(fixture_client, lake, 1255, NOW)
    calls = {}

    def fake_loader(table, uris):
        calls[table] = uris
        return len(uris)

    result = load(lake, fake_loader)
    assert result["openf1_laps"] == 1
    assert set(calls) == set(result)


def test_load_refuses_an_empty_lake(lake):
    with pytest.raises(ValueError, match="no complete meetings"):
        load(lake, lambda table, uris: 0)


def test_bigquery_loader_truncates_and_loads_parquet():
    class Job:
        output_rows = 42

        def result(self):
            return self

    class FakeClient:
        def load_table_from_uri(self, uris, destination, job_config):
            self.call = (uris, destination, job_config)
            return Job()

    client = FakeClient()
    loader = bigquery_loader("pitwall-tr-dev", client=client)
    assert loader("openf1_laps", ["gs://b/raw/laps/x.parquet"]) == 42
    uris, destination, config = client.call
    assert destination == f"pitwall-tr-dev.{RAW_DATASET}.openf1_laps"
    assert config.source_format == "PARQUET"
    assert config.write_disposition == "WRITE_TRUNCATE"
```

Append to `projects/pitwall/tests/test_cli.py`:

```python
def test_load_refuses_a_local_lake(lake_env, monkeypatch, capsys):
    monkeypatch.setenv("PITWALL_BQ_PROJECT", "pitwall-tr-dev")
    with pytest.raises(SystemExit) as exit_info:
        main(["load"])
    assert exit_info.value.code == 2
    assert "gs://" in capsys.readouterr().err


def test_load_requires_a_bigquery_project(monkeypatch, capsys):
    monkeypatch.setenv("PITWALL_LAKE_URI", "gs://pitwall-tr-dev-raw")
    monkeypatch.delenv("PITWALL_BQ_PROJECT", raising=False)
    with pytest.raises(SystemExit) as exit_info:
        main(["load"])
    assert exit_info.value.code == 2
    assert "PITWALL_BQ_PROJECT" in capsys.readouterr().err
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_load.py tests/test_cli.py -q`
Expected: collection error `No module named 'pitwall.load'`; after that exists, the CLI tests fail with `invalid choice: 'load'`.

- [ ] **Step 4: Implement `load.py`**

`projects/pitwall/src/pitwall/load.py`:

```python
"""Rebuild BigQuery raw tables from the lake: full reload, marked meetings only."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from pitwall.contracts import CONTRACTS
from pitwall.lake import Lake, meeting_file, season_file

log = logging.getLogger(__name__)

RAW_DATASET = "raw"
Loader = Callable[[str, list[str]], int]


def load_plan(lake: Lake) -> dict[str, list[str]]:
    """Map each raw table to the lake URIs it is rebuilt from.

    Only meetings with a success marker count, and only the endpoints their manifest lists,
    so a crashed or older ingestion can never make a load job reference a missing file.
    """
    manifests = lake.manifests()
    seasons = sorted({m["season"] for m in manifests})
    plan = {}
    for endpoint, contract in CONTRACTS.items():
        if contract.level == "season":
            rels = [season_file(endpoint, s) for s in seasons]
            rels = [rel for rel in rels if lake.exists(rel)]
        else:
            rels = [
                meeting_file(endpoint, m["season"], m["meeting_key"])
                for m in sorted(manifests, key=lambda m: m["meeting_key"])
                if endpoint in m["rows"]
            ]
        plan[f"openf1_{endpoint}"] = [lake.uri_of(rel) for rel in rels]
    return plan


def load(lake: Lake, loader: Loader) -> dict[str, int]:
    """Run one load per raw table; returns rows loaded per table."""
    plan = load_plan(lake)
    if not any(plan.values()):
        raise ValueError("the lake has no complete meetings to load")
    loaded = {}
    for table, uris in plan.items():
        if not uris:
            log.warning("%s: nothing to load; table left as is", table)
            continue
        loaded[table] = loader(table, uris)
        log.info("%s: %d rows from %d files", table, loaded[table], len(uris))
    return loaded


def bigquery_loader(
    project: str, dataset: str = RAW_DATASET, client: Any = None
) -> Loader:
    """A loader that replaces `project.dataset.<table>` with the given Parquet files."""
    from google.cloud import bigquery

    client = client or bigquery.Client(project=project)
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    def load_table(table: str, uris: list[str]) -> int:
        job = client.load_table_from_uri(
            uris, f"{project}.{dataset}.{table}", job_config=config
        )
        return job.result().output_rows

    return load_table
```

- [ ] **Step 5: Add the `load` command to `cli.py`**

In `projects/pitwall/src/pitwall/cli.py`:
- add `from pitwall.load import bigquery_loader, load` to the imports;
- after the `ingest` sub-parser block, add `commands.add_parser("load", help="rebuild BigQuery raw tables from the lake")`;
- replace everything from `if args.season is not None and args.season < FIRST_SEASON:` to the end of `main` with:

```python
if args.command == "ingest" and args.season is not None and args.season < FIRST_SEASON:
    parser.error(f"OpenF1 has data from {FIRST_SEASON} onwards")
lake_uri = os.environ.get("PITWALL_LAKE_URI")
if not lake_uri:
    parser.error("PITWALL_LAKE_URI is not set (a path, file:// or gs:// URI)")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
lake = Lake(lake_uri)

if args.command == "load":
    project = os.environ.get("PITWALL_BQ_PROJECT")
    if not project:
        parser.error(
            "PITWALL_BQ_PROJECT is not set (the GCP project holding the raw dataset)"
        )
    if lake.is_local:
        parser.error(
            "BigQuery can only load from a gs:// lake; set PITWALL_LAKE_URI=gs://..."
        )
    loaded = load(lake, bigquery_loader(project))
    log.info("loaded %d tables, %d rows", len(loaded), sum(loaded.values()))
    return 0

client = client or OpenF1Client()
now = now or datetime.now(UTC)
if args.latest:
    done = ingest_latest(client, lake, now)
elif args.meeting is not None:
    done = ingest_one(client, lake, args.meeting, now)
else:
    done = ingest_season(client, lake, args.season, now)
log.info(
    "ingested %d meeting(s) %s using %d requests", len(done), done, client.request_count
)
return 0
```

Note: `Lake("gs://...")` must not touch the network at construction (pyarrow's `GcsFileSystem` is lazy); `test_load_requires_a_bigquery_project` proves it.

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -q && uv run ruff check --fix . && uv run ruff format .`
Expected: 56 passed; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/pitwall/load.py src/pitwall/cli.py tests/test_load.py tests/test_cli.py
git commit -m "feat(pitwall): load raw tables into BigQuery from marked meetings"
```

---

### Task 3: Terraform root

**Files:**
- Create: `projects/pitwall/infra/gcp/versions.tf`, `variables.tf`, `main.tf`, `iam.tf`, `outputs.tf`, `.terraform.lock.hcl` (generated)

**Interfaces:**
- Variables: `env` (dev|prod), `project_id`, `region` (default `us-central1`), `github_repository` (default `TomasRipsky/data-engineering-lab`), `github_repository_id` (default `"1396373223"`), `query_quota_mib_per_day` (default `51200` = 50 GiB).
- Outputs: `lake_uri`, `pipeline_service_account`, `dashboard_service_account` (null in dev), `workload_identity_provider`.

- [ ] **Step 1: `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# ADC from `gcloud auth application-default login`; bill API calls to the project itself.
provider "google" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}
```

- [ ] **Step 2: `variables.tf`**

```hcl
variable "env" {
  description = "Environment name."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "project_id" {
  description = "GCP project created by `make bootstrap`."
  type        = string
}

variable "region" {
  description = "Region for the lake bucket and BigQuery datasets (GCS free tier regions only)."
  type        = string
  default     = "us-central1"
}

variable "github_repository" {
  description = "owner/name of the repository allowed to use Workload Identity Federation."
  type        = string
  default     = "TomasRipsky/data-engineering-lab"
}

variable "github_repository_id" {
  description = "Immutable numeric ID of that repository (a renamed or recreated repo gets a new one)."
  type        = string
  default     = "1396373223"
}

variable "query_quota_mib_per_day" {
  description = "Hard cap on BigQuery bytes scanned per day in this project, in MiB."
  type        = number
  default     = 51200
}
```

- [ ] **Step 3: `main.tf` — APIs, lake, datasets, quota**

```hcl
locals {
  apis     = ["bigquery.googleapis.com", "storage.googleapis.com", "iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com"]
  datasets = ["raw", "staging", "intermediate", "marts"]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# The lake is regenerable from OpenF1, so destroy may delete it with its contents (ADR 0005).
resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-raw"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "layers" {
  for_each                   = toset(local.datasets)
  dataset_id                 = each.value
  location                   = var.region
  delete_contents_on_destroy = true

  depends_on = [google_project_service.apis]
}

# A budget alert only warns; this quota stops runaway queries.
resource "google_service_usage_consumer_quota_override" "bigquery_query_per_day" {
  provider       = google-beta
  service        = "bigquery.googleapis.com"
  metric         = urlencode("bigquery.googleapis.com/quota/query/usage")
  limit          = urlencode("/d/project")
  override_value = var.query_quota_mib_per_day
  force          = true

  depends_on = [google_project_service.apis]
}
```

- [ ] **Step 4: `iam.tf` — service accounts and Workload Identity Federation**

```hcl
resource "google_service_account" "pipeline" {
  account_id   = "pitwall-pipeline"
  display_name = "pitwall pipeline (${var.env})"
}

resource "google_storage_bucket_iam_member" "pipeline_lake" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.pipeline.member
}

resource "google_bigquery_dataset_iam_member" "pipeline_datasets" {
  for_each   = google_bigquery_dataset.layers
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.pipeline.member
}

resource "google_project_iam_member" "pipeline_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.pipeline.member
}

resource "google_service_account" "dashboard" {
  count        = var.env == "prod" ? 1 : 0
  account_id   = "pitwall-dashboard"
  display_name = "pitwall dashboard reader"
}

resource "google_bigquery_dataset_iam_member" "dashboard_marts" {
  count      = var.env == "prod" ? 1 : 0
  dataset_id = google_bigquery_dataset.layers["marts"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = google_service_account.dashboard[0].member
}

resource "google_project_iam_member" "dashboard_jobs" {
  count   = var.env == "prod" ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.dashboard[0].member
}

# Deleted pools stay reserved for 30 days: a suffix lets destroy → apply work immediately.
resource "random_id" "pool" {
  byte_length = 2
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-${random_id.pool.hex}"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions OIDC"

  attribute_mapping = merge(
    {
      "google.subject"       = "assertion.sub"
      "attribute.repository" = "assertion.repository"
    },
    var.env == "prod" ? { "attribute.environment" = "assertion.environment" } : {},
  )

  # Without a condition any GitHub repository could exchange tokens here.
  attribute_condition = join(" && ", compact([
    "assertion.repository_id == '${var.github_repository_id}'",
    var.env == "prod" ? "assertion.environment == 'prod'" : "",
  ]))

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

locals {
  github_principal = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_service_account_iam_member" "pipeline_wif" {
  service_account_id = google_service_account.pipeline.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_principal
}

resource "google_service_account_iam_member" "dashboard_wif" {
  count              = var.env == "prod" ? 1 : 0
  service_account_id = google_service_account.dashboard[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_principal
}
```

- [ ] **Step 5: `outputs.tf`**

```hcl
output "lake_uri" {
  value = "gs://${google_storage_bucket.raw.name}"
}

output "pipeline_service_account" {
  value = google_service_account.pipeline.email
}

output "dashboard_service_account" {
  value = var.env == "prod" ? google_service_account.dashboard[0].email : null
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}
```

- [ ] **Step 6: Format, init and validate (no cloud resources yet)**

Run: `cd projects/pitwall && terraform -chdir=infra/gcp fmt && terraform -chdir=infra/gcp init -input=false && terraform -chdir=infra/gcp validate`
Expected: `Success! The configuration is valid.` and a generated `.terraform.lock.hcl`. If `~> 7.0` does not resolve, use the current major the registry offers and note the ruling.

- [ ] **Step 7: Commit**

```bash
git add infra/gcp/*.tf infra/gcp/.terraform.lock.hcl
git commit -m "feat(pitwall): add Terraform for the lake, datasets, service accounts and WIF"
```

---

### Task 4: Makefile environments

**Files:**
- Modify: `projects/pitwall/Makefile`, `projects/pitwall/.env.example`

- [ ] **Step 1: Replace the Makefile header and the `destroy` target**

Replace the lines from `.PHONY` through `export PITWALL_LAKE_URI ?= .lake` with:

```make
.PHONY: setup test lint fmt ingest load bootstrap init plan apply destroy

ENV ?= dev
PROJECT_PREFIX ?= pitwall-tr
PROJECT_ID := $(PROJECT_PREFIX)-$(ENV)
TF := terraform -chdir=infra/gcp
TF_VARS := -var env=$(ENV) -var project_id=$(PROJECT_ID)

# Override with a local path (e.g. PITWALL_LAKE_URI=.lake) to work offline.
export PITWALL_LAKE_URI ?= gs://$(PROJECT_ID)-raw
export PITWALL_BQ_PROJECT ?= $(PROJECT_ID)

ifeq ($(filter $(ENV),dev prod),)
$(error ENV must be dev or prod, got '$(ENV)')
endif
```

Replace the `destroy` target with:

```make
load: ## Rebuild BigQuery raw tables in $(PROJECT_ID) from the lake
	uv run pitwall load

bootstrap: ## One-off per env: create project, link billing, budget alert. BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX
	@test -n "$(BILLING_ACCOUNT)" || { echo "set BILLING_ACCOUNT (see: gcloud billing accounts list)"; exit 1; }
	gcloud projects create $(PROJECT_ID) --name="pitwall $(ENV)"
	gcloud billing projects link $(PROJECT_ID) --billing-account=$(BILLING_ACCOUNT)
	gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com billingbudgets.googleapis.com --project=$(PROJECT_ID)
	gcloud billing budgets create --billing-account=$(BILLING_ACCOUNT) --billing-project=$(PROJECT_ID) \
	  --display-name="pitwall-$(ENV)" --budget-amount=5USD --filter-projects=projects/$(PROJECT_ID) \
	  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0

init:
	$(TF) init -input=false
	$(TF) workspace select -or-create $(ENV)

plan: init ## Show infrastructure changes for ENV
	$(TF) plan $(TF_VARS)

apply: init ## Create/update infrastructure for ENV (cost: US$0/month expected)
	$(TF) apply $(TF_VARS)

destroy: init ## Delete every resource Terraform created in ENV (lake data included)
	$(TF) destroy $(TF_VARS)
```

- [ ] **Step 2: `.env.example`**

Replace its `PITWALL_LAKE_URI` lines with:

```
# Root of the raw lake: gs://<project>-raw (default via make) or a local path like .lake
PITWALL_LAKE_URI=gs://pitwall-tr-dev-raw
# GCP project whose `raw` dataset `pitwall load` rebuilds
PITWALL_BQ_PROJECT=pitwall-tr-dev
```

- [ ] **Step 3: Check the Makefile without touching the cloud**

Run: `make -n apply && make -n ENV=prod plan && make -n ENV=staging plan; echo "exit=$?"`
Expected: the first two print terraform commands with `-var env=dev -var project_id=pitwall-tr-dev` / `…prod`; the third fails with `ENV must be dev or prod, got 'staging'`.

- [ ] **Step 4: Commit**

```bash
git add Makefile .env.example
git commit -m "feat(pitwall): add per-environment make targets for bootstrap, terraform and load"
```

---

### Task 5: Stand up dev and prove the cycle

**Files:** none (operations). Record every command's outcome in the ledger.

- [ ] **Step 1: HARD STOP — confirm cost with Tomas**

Tell Tomas, and wait for an explicit yes: "About to create GCP project `pitwall-tr-dev`, link it to billing, add a US$5 budget alert, then `terraform apply` a bucket, 4 datasets, 1 service account, a WIF pool and a query quota. Expected cost: US$0/month (MBs of storage, tiny queries, all within free tier). Proceed?"

- [ ] **Step 2: Bootstrap dev**

Run: `cd projects/pitwall && make bootstrap BILLING_ACCOUNT=<id from gcloud billing accounts list>`
Expected: project created, billing linked, budget created. If the project ID is taken, rerun with `PROJECT_PREFIX=<another>` everywhere and ledger it.

- [ ] **Step 3: Verify the quota metric names before applying**

Run: `gcloud services enable bigquery.googleapis.com --project=pitwall-tr-dev && gcloud alpha services quota list --service=bigquery.googleapis.com --consumer=projects/pitwall-tr-dev --filter="metric=bigquery.googleapis.com/quota/query/usage" --format=yaml | head -40`
Expected: a limit with `unit: 1/d/{project}` and a MiB-based value. If metric, limit or unit differ, fix `main.tf` to match, re-run `validate`, and ledger the ruling. If the metric is absent, delete the quota resource, set the cap by hand in the console, and document that in the README (spec §13 fallback).

- [ ] **Step 4: Plan and apply**

Run: `make plan` and read it (expect ~20 resources to add, 0 to destroy); then `make apply`.
Expected: apply complete; outputs show `lake_uri = "gs://pitwall-tr-dev-raw"`.

- [ ] **Step 5: Ingest the 2025 season into GCS and load**

Run: `make ingest ARGS="--season 2025"` (~20 min), then `make load`.
Expected: ingest logs `ingested 2x meeting(s)`; load logs one line per table and `loaded 12 tables`.

- [ ] **Step 6: Verify in BigQuery**

Run: `bq --project_id=pitwall-tr-dev query --use_legacy_sql=false 'select count(*) as laps, count(distinct meeting_key) as meetings from raw.openf1_laps'`
Expected: tens of thousands of laps, meetings equal to the number ingested. Re-run `make load` and check the count is unchanged (WRITE_TRUNCATE is idempotent).

- [ ] **Step 7: Prove teardown and recreation**

Run: `make destroy`, then `gcloud storage ls gs://pitwall-tr-dev-raw` (expect "not found"), then `make apply`, then `make ingest ARGS="--meeting 1255" && make load`.
Expected: destroy removes everything; apply succeeds again (new WIF pool suffix); the reloaded `raw.openf1_laps` holds the 2025 Chinese GP only. Re-run the 2025 season ingest + load afterwards so dev keeps a full season (Plan 3 needs it).

---

### Task 6: Decisions, docs, knowledge and PR

**Files:**
- Create: `projects/pitwall/docs/decisions/0003-gcp-two-projects-bigquery-only.md`, `0004-full-reload-of-raw-tables.md`, `0005-regenerable-storage-is-force-destroyed.md`
- Modify: `projects/pitwall/README.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-09-29-pitwall-design.md`

- [ ] **Step 1: ADR 0003**

```markdown
# 0003 — GCP with one project per environment; BigQuery only

- **Status:** Accepted
- **Date:** 2026-09-30

## Context
Dev and prod must be isolated and free; CI must test dbt models without a laptop.

## Decision
Two GCP projects (`pitwall-tr-dev`, `pitwall-tr-prod`) created by `make bootstrap`, with identical
Terraform-managed contents. BigQuery is the only warehouse: dev and CI (ephemeral `ci_pr_<n>_*`
datasets) run in the dev project.

## Alternatives considered
- One project with prefixed buckets/datasets — weaker isolation (shared IAM and quotas).
- DuckDB for dev/CI — dropped once dev lives in the cloud: two SQL dialects are a permanent tax.
- Projects created by Terraform — needs org/billing-level permissions we don't want to manage.

## Consequences
- Free tier is per billing account, so two projects cost nothing extra.
- Bootstrap (project, billing link, budget) is a documented manual step outside Terraform state.
```

- [ ] **Step 2: ADR 0004**

```markdown
# 0004 — Full reload of raw tables

- **Status:** Accepted
- **Date:** 2026-09-30

## Context
Raw tables must mirror the lake exactly and idempotently.

## Decision
`pitwall load` rebuilds every `raw.openf1_*` table with one `WRITE_TRUNCATE` Parquet load job, from
an explicit URI list built from success markers and their manifests (never a wildcard).

## Alternatives considered
- Partition-level loads (`table$meeting_key`) — more moving parts for megabytes of data.
- External tables over GCS — no load step, but slower queries and hive-path coupling.

## Consequences
- Load jobs are free, atomic per table and trivially idempotent.
- Cost grows with total data; revisit with telemetry (phase 2), where partition loads pay off.
```

- [ ] **Step 3: ADR 0005**

```markdown
# 0005 — Regenerable storage is force-destroyed

- **Status:** Accepted
- **Date:** 2026-09-30

## Context
`make destroy` must remove everything, but GCS refuses to delete non-empty buckets and BigQuery
refuses to delete non-empty datasets.

## Decision
Set `force_destroy` on the lake bucket and `delete_contents_on_destroy` on all datasets.

## Alternatives considered
- Manual emptying before destroy — error-prone and undocumented.
- Keep data on destroy — leaves billable leftovers behind.

## Consequences
- Destroy is one command. Acceptable only because all data is regenerable from OpenF1
  (~1 h full backfill); this setting would be wrong for irreplaceable data.
```

- [ ] **Step 4: README — run instructions, cost & teardown**

In `projects/pitwall/README.md`:
- mermaid: change `lake -. Plan 2 .-> bq[(BigQuery)]` to `lake --> load[pitwall load] --> bq[(BigQuery raw)]`;
- add Tech stack rows `Warehouse | BigQuery (raw dataset, full reload) | Free tier, load jobs are free — ADR 0003/0004` and `Infrastructure | Terraform + make bootstrap | One root, workspace per env, no keys (WIF)`;
- replace "Run it" with:

````markdown
```bash
make setup && make test
# one-off per environment (creates the GCP project + US$5 budget alert):
make bootstrap BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX
make apply                          # ENV=dev by default
make ingest ARGS="--season 2025"    # OpenF1 → gs://pitwall-tr-dev-raw (~20 min, 30 req/min limit)
make load                           # lake → BigQuery raw.openf1_* tables
```
````

- replace "Cost & teardown" body with:

````markdown
Per environment: one GCP project with a GCS bucket (MBs), four BigQuery datasets, service accounts
and a Workload Identity pool. **Expected cost: US$0/month** — all within free tier. Guards: a
US$5 budget alert (warns) and a 50 GiB/day BigQuery query quota (stops).

```bash
make destroy ENV=dev                 # deletes everything Terraform created, lake data included
gcloud projects delete pitwall-tr-dev  # nuclear option: the project, budget filter and all
```
````

- [ ] **Step 5: Spec amendments**

In `docs/superpowers/specs/2026-09-29-pitwall-design.md`:
- §4 manifest bullet: replace "The manifest lists endpoints, row counts, request URLs and `_ingested_at`." with "The manifest lists row counts per endpoint (its keys are the endpoints the loader may read), the request count and `_ingested_at`; request URLs are reproducible from the path and were dropped."
- §9 Bootstrap: project IDs are `pitwall-tr-<env>`; only dev is created before Plan 4.
- §9 Terraform: datasets use `delete_contents_on_destroy`; the WIF pool ID carries a random suffix (pools stay reserved 30 days after deletion); WIF conditions use the immutable repository ID; the quota uses `google-beta`.
- §13: mark "BigQuery custom quota settable via Terraform" resolved (beta provider) and add "pyarrow `create_dir` creates GCS buckets → lake never calls it on object stores".

- [ ] **Step 6: CHANGELOG, commit, push, PR, review, merge**

Add under `## [Unreleased]` → `### Added`:
`- \`pitwall\`: GCP dev environment (Terraform, WIF, quota, budget) and \`pitwall load\` rebuilding BigQuery raw tables from the lake.`

```bash
cd "/Users/tomasripsky/Data Engineering/Claude Code Enviroment"
git add projects/pitwall docs/superpowers/specs CHANGELOG.md
git commit -m "docs(pitwall): add infra ADRs, cost and teardown, spec amendments"
git push -u origin HEAD
gh pr create --base dev --title "feat(pitwall): GCP infrastructure and BigQuery loader" --body "Closes #<issue>"
```

Run the `pr-reviewer` agent (include this plan's Review Focus), fix Critical/Important findings with tests, then squash-merge (Tomas authorized merges on 2026-09-30).

- [ ] **Step 7: Second brain**

Enrich (don't duplicate) vault notes: **Infrastructure as Code / Terraform** (workspaces, state, bootstrap outside state), a new **Workload Identity Federation** concept note (OIDC token exchange, attribute conditions, why immutable IDs), and **Cost control** (budget warns vs quota stops) — link all from `07 - Laboratory/pitwall.md` and update its "Next experiment" to Plan 3. Commit and push the vault.
