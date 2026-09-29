# pitwall

> Batch ELT over Formula 1 data (OpenF1 → GCS → BigQuery → dbt → Evidence) that explains race strategy — tyres, pit stops and the undercut — to people who don't follow F1.

## Architecture

```mermaid
flowchart LR
  source[Source] --> ingest[Ingest] --> storage[(Storage)] --> transform[Transform] --> serve[Serve]
```

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Ingestion | | |
| Storage | | |
| Transformation | | |
| Orchestration | | |

## Run it

```bash
make setup
make test
```

## Cost & teardown

Cloud resources used, expected monthly cost (target: free tier) and how to remove everything:

```bash
make destroy
```

## Decisions

Architecture Decision Records live in [docs/decisions/](docs/decisions/).

## What I learned

- Concept — one line on the insight (second-brain note: `02 - Fundamentals/...`).
