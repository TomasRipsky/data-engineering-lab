# 0002 — Lake-first ingestion with a custom extractor

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
We need to move OpenF1 data into a warehouse, idempotently, with backfills, while keeping the
design portable across clouds and teaching the fundamentals.

## Decision
A small Python extractor writes contract-checked Parquet to an object-store "lake"
(`raw/<endpoint>/season=/meeting_key=/`) with a success marker per meeting; the warehouse loads
from the lake.

## Alternatives considered
- dlt — less code and schema inference, but hides exactly what this project is meant to teach.
  Revisit once the fundamentals are in place.
- Direct API → warehouse inserts — simplest, but no replay and couples extraction to one warehouse.

## Consequences
- Replays and model changes never re-hit the API.
- Portability: only the lake URI changes between local, GCS and S3.
- We own ~300 lines of code: rate limiting, retries, contracts and atomic markers.
