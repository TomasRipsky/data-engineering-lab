# Agent changelog

What changed in how Claude works in this lab, and why. The lab's own releases are in the root [`CHANGELOG.md`](../CHANGELOG.md).
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- **Agent docs separated from project docs (Lab 1.0).** `agent/` (how I work), `lab/` (rules of the world) and `projects/` (countries) replace the mixed `docs/` folder and a `CLAUDE.md` that held everything — the pitwall retro found the docs scattered and hard to trace ([lab ADR 0006](../lab/adr/0006-world-and-countries-structure.md)).
- **`CLAUDE.md` is now a constitution:** hard rules always loaded, procedures moved to skills, full references to `lab/` — a rule that is not loaded is a rule that gets broken.
- **Tutoring protocol adopted:** brief → execute → tutor review → vault note, per logical block — in pitwall Tomas finished without understanding the dbt logic; an end-of-task "Why" block was not enough.
- **Quality-first premise for my own config:** files may grow when the cost-benefit justifies it; waste is the enemy, not length.
- **Continuous self-improvement:** lessons are applied when detected, experimentally and reversibly, instead of waiting for retros.
- **Leaner plans for docs-only work:** plan A of Lab 1.0 specifies documents by required content instead of full text (~400 lines vs ~2,500 for a pitwall plan). Under evaluation.
