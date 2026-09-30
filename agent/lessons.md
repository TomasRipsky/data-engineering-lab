# Lessons

Lessons learned the hard way, each turned into a rule that prevents it. A lesson is applied **when it is detected** — the fix goes into the skill, hook, `CLAUDE.md` or memory right away, and is reverted if it does not work. Retros review this file; they are not the only time it grows.

## Format

```markdown
### <short title>
- **Symptom:** what went wrong, as observed.
- **Cause:** why it happened.
- **Rule:** what I do now instead.
- **Applied in:** the commit, skill, hook or file that enforces the rule.
```

## Lessons

<!-- The pitwall retro lessons are added in Lab 1.0 plan B. -->

### Moving files changes how tools see them
- **Symptom:** moving pitwall's historical plans under `projects/pitwall/` made the `ruff-format` pre-commit hook rewrite 160+ lines of Python code blocks inside them, and the commit failed.
- **Cause:** ruff ≥ 0.16 formats Python blocks in Markdown and resolves its settings from the nearest `pyproject.toml` — the moved files inherited pitwall's `line-length = 100`. A rename counts as a changed file, so the hook ran on them.
- **Rule:** before a move, ask which tools resolve configuration by location (ruff, dbt, Terraform, pytest). Keep moves and edits in separate commits so git still detects the rename. Records (specs, plans) are excluded from formatters.
- **Applied in:** ruff config of every project (`extend-exclude = ["docs/design"]` in `projects/*/pyproject.toml`, so `make lint` and pre-commit agree) and a root `ruff.toml` for `lab/design` — one place per scope, honoured by `make lint`, `ruff` and pre-commit alike; lab ADR 0006.
- **Follow-up:** the first fix lived only in pre-commit, so `make lint` still failed; the reviewer then found the lab-level exclude had the same flaw. Exclude in the *tool's* config, not in one caller of the tool.
