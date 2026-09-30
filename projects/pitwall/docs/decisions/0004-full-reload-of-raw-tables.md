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
