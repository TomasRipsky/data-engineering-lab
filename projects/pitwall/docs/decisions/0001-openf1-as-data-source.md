# 0001 — OpenF1 as the data source

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
The first lab project needs a free, frequently updated API with history (for incremental loads and
backfills) and a story that catches attention in a portfolio.

## Decision
Use OpenF1 (historical Formula 1 data from 2023, no API key, 30 req/min free tier), restricted to
Race and Sprint sessions for a race-strategy story.

## Alternatives considered
- OpenSky (flights) — REST only serves the last hour; history needs research access. A streaming
  source: kept for the streaming project.
- Lichess/Chess.com — fun, but monthly dumps are tens of GB.
- Steam player counts — no history via API.
- NASA NEO — low volume and little modelling depth.

## Consequences
- New data every race weekend makes scheduling and idempotency meaningful.
- The 30 req/min limit forces a polite client (limiter + backoff).
- Educational/non-commercial terms: fine for a portfolio, not for a product.
- Quirks to live with: "no data" is HTTP 404; `starting_grid` hangs off qualifying sessions;
  some 2023 races have no `pit` data.
