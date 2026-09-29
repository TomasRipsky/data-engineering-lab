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
