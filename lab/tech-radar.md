# Tech radar

What this lab uses, is trying, is looking at, and has put on hold — in the rings of the [ThoughtWorks Technology Radar](https://www.thoughtworks.com/radar). Each entry says **why** and links to the decision or project that earned it. A tech moves rings only through a project or an ADR.

Private ideas, business notes and the full project backlog live in Tomas's private vault, not here.

## Adopt — proven here, default choice

| Tech | Why | Evidence |
|---|---|---|
| Python + uv, ruff, pytest | Fast, reproducible, one tool per job | [lab ADR 0002](adr/0002-python-tooling-uv-ruff-pytest.md) |
| dbt | SQL as software: tests, lineage, docs, environments; industry default for warehouse transformation | [pitwall](../projects/pitwall/) |
| BigQuery | Serverless warehouse, generous free tier, free load jobs | [pitwall ADR 0003](../projects/pitwall/docs/decisions/0003-gcp-two-projects-bigquery-only.md), [0004](../projects/pitwall/docs/decisions/0004-full-reload-of-raw-tables.md) |
| Google Cloud Storage | Cheap raw lake that BigQuery loads natively; the lake is the replayable source of truth | [pitwall ADR 0002](../projects/pitwall/docs/decisions/0002-lake-first-custom-extractor.md) |
| Terraform | Industry-standard IaC, multi-cloud, `make destroy` for free | [pitwall infra](../projects/pitwall/infra/gcp/) |
| GitHub Actions + Workload Identity Federation | Free for public repos, keyless cloud auth | [pitwall ADR 0006](../projects/pitwall/docs/decisions/0006-github-actions-as-orchestrator.md) |
| Observable Framework | Static, keyless data site with full design control | [pitwall ADR 0007](../projects/pitwall/docs/decisions/0007-observable-framework-for-the-dashboard.md), [lab ADR 0005](adr/0005-one-lab-site-with-a-shared-design.md) |

## Trial — being tried in the next project

| Tech | Why |
|---|---|
| Looker Studio | Industry-standard self-service BI on BigQuery; pitwall BI is next. Rejected earlier for the *public site* (click-ops), which Observable still owns. |
| Grafana | Industry-standard observability dashboards: pipeline runs, data freshness, cloud cost. |

## Assess — worth understanding, no project yet

| Tech | Why |
|---|---|
| Apache Kafka | The default event-streaming backbone: partitions, offsets, replay. |
| Apache Spark | Distributed processing at scale; the core of Databricks. |
| Apache Iceberg / Delta Lake | Open table formats: lakehouse without a warehouse lock-in. |
| Apache Airflow | Most-used orchestrator; compare against GitHub Actions' limits. |
| Databricks | Leading lakehouse platform; multi-cloud. |
| Docker | Reproducible local stacks (Kafka, Spark, Postgres) and container-based deploys. |

## Hold — not now, and why

| Tech | Why |
|---|---|
| Evidence (BI-as-code) | Its current line needs a long-lived BigQuery key; the keyless line is no longer maintained — [pitwall ADR 0007](../projects/pitwall/docs/decisions/0007-observable-framework-for-the-dashboard.md). |
