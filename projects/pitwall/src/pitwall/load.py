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


def bigquery_loader(project: str, dataset: str = RAW_DATASET, client: Any = None) -> Loader:
    """A loader that replaces `project.dataset.<table>` with the given Parquet files."""
    from google.cloud import bigquery

    client = client or bigquery.Client(project=project)
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    def load_table(table: str, uris: list[str]) -> int:
        job = client.load_table_from_uri(uris, f"{project}.{dataset}.{table}", job_config=config)
        return job.result().output_rows

    return load_table
