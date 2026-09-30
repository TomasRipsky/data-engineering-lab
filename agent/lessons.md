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
- **Cause:** unknown, and intermittent: GitHub registers the link (`closingIssuesReferences` lists the issue), so parsing is not the problem, and waiting 30+ minutes did not help. With the same flow, #32 (PR #33) stayed open while #34 (PR #35, merged by the `ship` skill with `--match-head-commit`) closed on its own.
- **Rule:** check the link before merging and the issue state after; close it manually with "Delivered by #<pr>" if still open.
- **Update (v1.0.0 release):** right after `gh pr create`, `closingIssuesReferences` can be empty for a few seconds (eventual consistency) — a check run immediately gives a false "not linked". The link check therefore runs as a gate just before the merge, not only right after creation.
- **Applied in:** `.claude/skills/ship/` (steps 3 and 7).

### A procedure is untested until its first real run
- **Symptom:** the first real run of the `ship` skill parsed an empty issue number from `feat/34-lab-1-0-agent`, although `bash -n` had passed.
- **Cause:** the snippet used `BASH_REMATCH`, which only exists in bash; the Bash tool here runs zsh. `bash -n` checks syntax, not behaviour, and only under bash.
- **Rule:** shell in skills must be portable across bash and zsh (prefer `sed`/`grep` over shell-specific features) and be exercised once on real input before it is trusted.
- **Applied in:** `.claude/skills/ship/` step 1.

### Shell variables do not survive between tool calls
- **Symptom:** `pr-reviewer` found that `ship` and `release` set `ISSUE`, `PR` and `V` in one bash block and used them in later ones. Run as separate calls they were empty — and `grep -qw ""` matches anything, so the issue-link check passed no matter what; `release` would have created a public issue titled "release v".
- **Cause:** each Bash tool call is a fresh shell (only the working directory persists); the skills were written as if they were one script.
- **Rule:** every bash block in a skill is self-contained — it derives its values again (`git branch`, `gh pr view`) or uses text substituted at invocation (`$ARGUMENTS`), and guards required values with `: "${VAR:?message}"`. Dependent steps go in the same block.
- **Applied in:** `.claude/skills/ship/` (steps 3, 6), `.claude/skills/release/`.

### Test permission rules with decoys, and know the matcher
- **Symptom:** while extending the deny rules, test results seemed to contradict the rules just written; `.env.example` was denied and `.env.local` allowed.
- **Cause:** three things at once. Claude Code reloads `settings.json` asynchronously, so a read right after an edit ran under the *previous* rules. Rule patterns have no bracket negation: `[!e]` and `[^e]` are literal classes (`{!, e}`, `{^, e}`). And the Read tool caches unchanged files, so re-reading a decoy proves nothing.
- **Rule:** test deny rules with decoy files whose content changes between rounds, re-test after the reload has had time to happen, cover both "must be denied" and "must stay readable"; enumerate names instead of relying on negation.
- **Applied in:** `.claude/settings.json`, `lab/security-and-cost.md`.

### A warning is not a gate
- **Symptom:** during the v1.0.0 release, `ship` step 3 printed "STOP: issue not linked", and the merge in step 6 ran anyway because both steps were executed in one scripted loop.
- **Cause:** step 3 only printed a message; nothing in step 6 depended on it. A human reads a STOP; a script (or an agent batching steps) does not.
- **Rule:** any check that must prevent an action lives in the same block as the action, as a condition on it. Messages are for information, conditions are for safety.
- **Applied in:** `.claude/skills/ship/` step 6 (link, pending, failing and head-commit gates before `gh pr merge`).

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

### A condensed guide loses what made the explanation work
- **Symptom:** the first pitwall guide section was a terse English digest of a much richer chat review; Tomas liked the chat version and asked whether it was being kept.
- **Cause:** I treated the guide as a summary of the review, while conversations are deleted — the chat was the only copy of the depth.
- **Rule:** the guide carries the review at full depth (flow, mechanisms, tables, alternatives, failure modes), plus a closing plain-language **In short** for retention.
- **Applied in:** `agent/tutoring.md` steps 3–4, CLAUDE.md tutoring step 3, `projects/_template/docs/guide.md`.
