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
