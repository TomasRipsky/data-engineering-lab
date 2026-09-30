# 0004 — Three-tier memory architecture

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Claude and Tomas will work together for years. Context must persist across sessions without every session paying to load everything. The system should get better, not bigger.

## Decision
- **Hot — Claude's file memory:** preferences, agreements, project state. Index ≤ ~40 lines, consolidated at each project retro.
- **Warm — this repo:** CLAUDE.md, ADRs, specs, git history. Read when working on it.
- **Deep — Obsidian vault** (`~/Data Engineering/Second Brain`, private repo `TomasRipsky/second-brain`): concepts, technologies, practices. Read on demand via grep and wikilinks.
- **graphify** is a derived index over repo and vault, built incrementally when it saves tokens; never the source of truth.

## Alternatives considered
- **Everything in CLAUDE.md** — loaded every session; grows until it hurts.
- **graphify graph as primary memory** — costs LLM tokens to build, not human-editable; derived data should not be canonical.
- **Learnings folder inside the repo** — duplicates the existing vault and exposes personal notes publicly.

## Consequences
Cheap sessions, durable knowledge. Requires discipline: consolidate memory at retros; merge vault notes instead of duplicating.
