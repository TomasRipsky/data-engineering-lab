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
- Budgets must use the billing account's currency (this account bills in EUR: 5 EUR).
