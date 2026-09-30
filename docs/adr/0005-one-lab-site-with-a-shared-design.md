# 0005 — One lab site with a shared design

- **Status:** Accepted
- **Date:** 2026-09-30

## Context
The lab is one repository with many projects, and GitHub Pages serves one site per repository.
Tomas wants every project's visualizations to look alike.

## Decision
A single Observable Framework site in `site/` is the lab's portfolio: a landing page plus one
section per project. Shared theme and components (`site/src/components/`, `site/src/style.css`)
and a fixed page skeleton ("What am I looking at?" → charts → limitations) keep projects
consistent. Projects hand the site **exported data files** (a tested per-project command writing
to `site/src/<project>/data/`), never live queries, so the site needs no knowledge of any
project's cloud or credentials.

## Alternatives considered
- One Pages site per project — impossible within one repo.
- A repository per project's site — scatters the portfolio and duplicates the design.
- Live queries from the site build — couples the site to every project's cloud and credentials.

## Consequences
- Today pitwall's pipeline exports, builds and deploys the whole site. When a second project needs
  the site, a lab-level `lab-site` workflow will gather every project's export and build once — a
  change of where files meet, not of the contract.
- Every deploy replaces the whole site, so until that workflow exists only pitwall may deploy.
- Shared structure, own personality: each section brings its own theme (e.g. pitwall's dark
  pit-wall look) on top of `components/lab.css`, and charts follow the `dataviz` skill.
