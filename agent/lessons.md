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

### Assumed instead of verified
- **Symptom:** in pitwall, GCP projects were first created outside the organisation, a budget was written in USD for a EUR billing account, a workflow pinned `astral-sh/setup-uv@v8` (no such tag), and the dashboard was designed on Evidence before checking it needed a long-lived BigQuery key.
- **Cause:** facts about accounts, billing, auth modes and versions came from memory, not from the source.
- **Rule:** before designing anything that touches accounts, billing, auth, CI or pinned versions, verify each fact at its source and write a dated "Verified facts" block into the spec; unverifiable facts are listed as assumptions with a task to check them first.
- **Applied in:** `.claude/skills/verify-before-design/`; CLAUDE.md "Verify, don't assume".

### Fragile Bash chaining
- **Symptom:** long `&&` / `;` chains mixing work, checks and bookkeeping hid which step failed, and a failed step once left half-done state (e.g. a ledger line written after a failed commit would have claimed success; in Lab 1.0 a `perl` substitution failed silently inside a chain and the commit went out without that change).
- **Cause:** one command doing several jobs; exit codes of middle steps lost; regex delimiters colliding with the text (`#` vs `##`).
- **Rule:** one purpose per command; bookkeeping only after the command it records succeeded (`&&`, never `;`); multi-line or delimiter-heavy edits use the Edit tool or a small script, not `sed`/`perl` one-liners; read every output.
- **Applied in:** `.claude/skills/ship/` (step 1); this file.

### Plans too long
- **Symptom:** pitwall plans reached ~2,500 lines, mostly code the executor then wrote again.
- **Cause:** the plan format asked for full code in every step, even for documents and repeated patterns.
- **Rule:** docs are specified by required content (checked by grep); code stays in full; a repeated pattern references the earlier plan instead of being rewritten.
- **Applied in:** Lab 1.0 plans A (~400 lines) and B (~170 lines); `agent/README.md` (Quality and cost).

### `Closes #n` did not close the issue
- **Symptom:** several PRs squash-merged into `dev` (the default branch) left their issue open although the body started with `Closes #n` — #33 included; #19 with the same format closed.
- **Cause:** unknown. GitHub does register the link (`closingIssuesReferences` lists the issue), so parsing is not the problem, and waiting 30+ minutes did not help.
- **Rule:** check the link before merging and the issue state after; close it manually with "Delivered by #<pr>" if still open.
- **Applied in:** `.claude/skills/ship/` (steps 3 and 7).

### A procedure is untested until its first real run
- **Symptom:** the first real run of the `ship` skill parsed an empty issue number from `feat/34-lab-1-0-agent`, although `bash -n` had passed.
- **Cause:** the snippet used `BASH_REMATCH`, which only exists in bash; the Bash tool here runs zsh. `bash -n` checks syntax, not behaviour, and only under bash.
- **Rule:** shell in skills must be portable across bash and zsh (prefer `sed`/`grep` over shell-specific features) and be exercised once on real input before it is trusted.
- **Applied in:** `.claude/skills/ship/` step 1.

### A hidden browser pane pauses Observable
- **Symptom:** while verifying the pitwall site, screenshots showed stale or empty charts although the data was right.
- **Cause:** browsers throttle hidden pages; Observable Framework's reactive runtime pauses when the pane is not visible.
- **Rule:** verify content with page text or the accessibility tree; keep the pane visible for visual checks.
- **Applied in:** this file (read before any site verification).

### Moving files changes how tools see them
- **Symptom:** moving pitwall's historical plans under `projects/pitwall/` made the `ruff-format` pre-commit hook rewrite 160+ lines of Python code blocks inside them, and the commit failed.
- **Cause:** ruff ≥ 0.16 formats Python blocks in Markdown and resolves its settings from the nearest `pyproject.toml` — the moved files inherited pitwall's `line-length = 100`. A rename counts as a changed file, so the hook ran on them.
- **Rule:** before a move, ask which tools resolve configuration by location (ruff, dbt, Terraform, pytest). Keep moves and edits in separate commits so git still detects the rename. Records (specs, plans) are excluded from formatters.
- **Applied in:** ruff config of every project (`extend-exclude = ["docs/design"]` in `projects/*/pyproject.toml`, so `make lint` and pre-commit agree) and a root `ruff.toml` for `lab/design` — one place per scope, honoured by `make lint`, `ruff` and pre-commit alike; lab ADR 0006.
- **Follow-up:** the first fix lived only in pre-commit, so `make lint` still failed; the reviewer then found the lab-level exclude had the same flaw. Exclude in the *tool's* config, not in one caller of the tool.
