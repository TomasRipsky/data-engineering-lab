# 0008 — Every project is shown with a story page and a BI page

- **Status:** Accepted
- **Date:** 2026-10-13

## Context
With one repository per project (ADR 0007) each project owns its public site. Three exist:
MarineFlow (hand-written HTML), CityPulse (Observable Framework, rebuilt in MarineFlow's spirit,
with a BI page) and pitwall (first a four-page dashboard). Tomas found the first two "the way to
show a project" and asked, on 2026-10-13, for pitwall to follow them and for that style to be the
standard from now on: a personality that represents the project's domain, pleasant to look at, as
complete as the data allows, with a BI-style section where possible.

ADR 0005's shared look was about consistency through a shared *site*. What is worth sharing turned
out to be the **shape of the story**, not the colours.

## Decision
Every project's site has two pages, built with Observable Framework:

1. **The story** (`index.md`), for a reader who knows neither the domain nor data engineering:
   sticky bar → illustrated hero with live numbers → the answers on domain-themed tiles → one
   section per question (what you are looking at → chart → its limits) → a case file chosen by a
   query → the pipeline drawn in the domain's language → decisions → quality → limits → run it.
2. **The BI page** (`bi.md`): a filter bar, KPIs that follow it, tables and charts per subject,
   CSV downloads, an empty state for every block.

Rules that make it trustworthy, not just pretty:

- **What the site reads is decided in dbt**: report models (`rpt_*`), one grain each, documented
  and tested. The export only copies them; every number is computed from those rows in the page,
  none is typed by hand.
- **Structure and theme are separate files.** `components/lab.css` and `lab.js` are the skeleton,
  identical in every project and seeded by `template/site/`; the project's stylesheet sets the
  `--lab-*` variables and adds only what belongs to its domain.
- Charts follow the `dataviz` skill; illustrations are original; no third-party requests;
  animation respects reduced motion; old URLs get redirects.

The full list lives in `template/site/README.md`, so `new-project` hands it to every new project.

## Alternatives considered
- **A dashboard with a sidebar** (pitwall's first site) — reads as a tool; the reader assembles the
  story from a menu, and the engineering behind it is invisible.
- **Hand-written HTML/JS** (MarineFlow) — full control, but every chart, input and responsive
  behaviour is written again in each project.
- **A shared component package** instead of copied files — one more thing to version and publish;
  the skeleton is two small files and projects are allowed to diverge when their domain asks for it.
- **A hosted BI tool** for the BI page — needs a server or a credential near the public
  (pitwall ADR 0007); a static page filtering exported files has neither.

## Consequences
- A new project starts with a working story and BI page and only has to bring its personality and
  its data.
- The case file doubles as a data test: choosing "the most extreme case" by query finds broken
  records first (pitwall's found a Safety Car period that never closed, pitwall#14).
- Report models add a small dbt layer to every project; in exchange the site's numbers are inside
  the project's tests, docs and lineage.
- Small exports are filtered in memory; a project whose page must aggregate large files uses
  DuckDB-WASM (`sql:` front matter), as CityPulse does. The standard is the page, not the engine.
- MarineFlow predates the standard and keeps its hand-written site until it is rebuilt.
