# Data Engineering Lab

Hands-on data engineering projects across clouds and open-source stacks — built to learn deeply and to show the work.

Each project is self-contained under [`projects/`](projects/) with its own README, architecture diagram, decisions (ADRs), tests and teardown instructions.

## Projects

| Project | What it does | Stack | Status |
|---|---|---|---|
| [pitwall](projects/pitwall/) | Batch ELT over Formula 1 data (OpenF1 → GCS → BigQuery → dbt → Evidence) that explains race strategy — tyres, pit stops and the undercut — to people who don't follow F1. | TBD | 🌱 bootstrapped |

## Getting started

```bash
git clone https://github.com/TomasRipsky/data-engineering-lab.git
cd data-engineering-lab
pre-commit install   # enables gitleaks, ruff and branch guards on every commit
```

## How this repo works

- **Branches:** `main` (releases) ← `dev` (integration) ← `<type>/<issue#>-<slug>` (work). Every change starts as an issue and lands through a pull request.
- **Decisions:** lab-wide ADRs in [`docs/adr/`](docs/adr/); project ADRs in each project's `docs/decisions/`.
- **Quality gates:** pre-commit with gitleaks (secret scanning) and ruff (lint + format).
- **Cost discipline:** free tier first, budget alerts, and `make destroy` in every cloud project.

Built in collaboration with [Claude Code](https://claude.com/claude-code).
