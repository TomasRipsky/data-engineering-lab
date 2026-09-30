# 0007 — Observable Framework for the dashboard (instead of Evidence)

- **Status:** Accepted (supersedes the spec's choice of Evidence)
- **Date:** 2026-09-30

## Context
The spec chose Evidence (BI-as-code) on GitHub Pages. Evidence's current line connects to BigQuery
**only with a service-account key file**; the organization forbids key creation
(`iam.disableServiceAccountKeyCreation`) and the project is keyless by design (WIF). The classic
Evidence line (40.x), whose connector supported ADC, has had no release since February 2026 while
the repository moved to the new product.

## Decision
Observable Framework, as the lab site (lab ADR 0005). pitwall's pages read Parquet files written by
`pitwall site-export`, which runs as the read-only dashboard account in prod.

## Alternatives considered
- Evidence (current) with a key — needs an org-policy exception and a long-lived secret.
- Evidence classic 40.x with `gcloud-cli` auth — works, but builds on a line its vendor abandoned.
- Looker Studio / Streamlit — rejected earlier (click-ops; runtime credentials and cold starts).

## Consequences
- Charts are ~20 lines of JavaScript each instead of prebuilt components: more control (the stint
  timeline), a little more code.
- The published site is fully static and keeps working even if the tool stops evolving; only
  rebuilds depend on it.
