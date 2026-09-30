# Project Name

> One-sentence pitch: what problem this solves and for whom.

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

## Docs

- [docs/guide.md](docs/guide.md) — how it works inside.
- [docs/design/](docs/design/) — the spec and implementation plans.
- [docs/decisions/](docs/decisions/) — Architecture Decision Records.

## What I learned

- Concept — one line on the insight (second-brain note: `02 - Fundamentals/...`).
