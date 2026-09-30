---
name: release
description: Cut a lab release vX.Y.Z — changelogs, PR dev → main with a merge commit, GitHub release.
disable-model-invocation: true
argument-hint: "[X.Y.Z]"
---

# Release v$ARGUMENTS

This skill only runs when Tomas types `/release X.Y.Z` — that is his explicit OK to merge `dev` into `main`. The GitHub release itself is public, so I still show him the notes before creating it.

**Consequences of merging into `main`:** if the release touches `projects/pitwall/**` or `site/**`, the push to `main` runs `pitwall-pipeline` on **prod** (reload + dbt rebuild from the lake, no API calls) and republishes the **public site**. Check with `git diff --stat origin/main origin/dev -- projects/pitwall site`, tell Tomas when starting, and make sure `dev` is in a state you would deploy.

Every bash block is self-contained (shell variables do not survive between tool calls): `$ARGUMENTS` is written into this text when the skill runs; anything else is derived again in the block that needs it.

## 1. Validate
```bash
[[ "$ARGUMENTS" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "not SemVer: $ARGUMENTS"; exit 1; }
git switch dev && git pull --ff-only
gh release view "v$ARGUMENTS" >/dev/null 2>&1 && { echo "v$ARGUMENTS already exists"; exit 1; }
awk '/^## \[Unreleased\]/{f=1;next}/^## \[/{f=0}f' CHANGELOG.md | grep -q '[^[:space:]]' || { echo "[Unreleased] is empty"; exit 1; }
echo "ok: v$ARGUMENTS can be released"
```
Check SemVer against the changes: breaking or structural → major; features → minor; fixes → patch. If the version looks wrong, say so before continuing.

## 2. Changelog PR into dev
```bash
URL=$(gh issue create --title "chore(lab): release v$ARGUMENTS" --label type:chore --label project:lab --body "Release v$ARGUMENTS.") || exit 1
N=${URL##*/}; [[ "$N" =~ ^[0-9]+$ ]] || { echo "unexpected gh output: $URL"; exit 1; }
git switch -c "chore/$N-release-v$ARGUMENTS"
```
In `CHANGELOG.md` and `agent/CHANGELOG.md`: rename `## [Unreleased]` to `## [$ARGUMENTS] - <today>` and add a fresh empty `## [Unreleased]` above it. Commit `chore(lab): release v$ARGUMENTS`, then follow the `ship` skill (steps 1–7) to land it in `dev`.

## 3. Release notes
Write the notes file once; later blocks read it from this fixed path:
```bash
NOTES="${TMPDIR:-/tmp}/release-v$ARGUMENTS.md"   # outside the repo
{ echo "## Lab"; awk -v v="$ARGUMENTS" '$0 ~ "^## \\[" v "\\]"{f=1;next}/^## \[/{f=0}f' CHANGELOG.md
  echo; echo "## Agent"; awk -v v="$ARGUMENTS" '$0 ~ "^## \\[" v "\\]"{f=1;next}/^## \[/{f=0}f' agent/CHANGELOG.md
  echo; echo "🤖 Generated with [Claude Code](https://claude.com/claude-code)"; } > "$NOTES"
# relative repo links do not resolve on the releases page: make them absolute to main
B="https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/blob/main"
perl -pi -e "s#\]\(\.\./#](#g; s#\]\((lab|agent|projects|site)/#]($B/\$1/#g" "$NOTES"
wc -l "$NOTES"
```

## 4. dev → main
```bash
git switch dev && git pull --ff-only
MAIN_PR=$(gh pr create --base main --head dev --title "release: v$ARGUMENTS" --body-file "${TMPDIR:-/tmp}/release-v$ARGUMENTS.md") || exit 1
echo "$MAIN_PR"
```
Wait for CI on that PR (read status once; do not poll). Then merge with a **merge commit**, never squash, so `main` keeps the release boundaries:
```bash
MAIN_PR=$(gh pr list --base main --head dev --state open --json number -q '.[0].number'); : "${MAIN_PR:?no open dev → main PR}"
gh pr merge "$MAIN_PR" --merge
```

## 5. GitHub release (public — show Tomas first)
Show Tomas the notes file and wait for his OK, then (replace the theme placeholder, as in earlier titles like `v0.4.0 — lab site and pitwall dashboard`):
```bash
gh release create "v$ARGUMENTS" --target main --title "v$ARGUMENTS — <one-line theme>" --notes-file "${TMPDIR:-/tmp}/release-v$ARGUMENTS.md"
git fetch -q origin && git diff --quiet origin/main origin/dev -- . && echo "main == dev"
```

## 6. After
Check that the prod pipeline run triggered by `main` succeeded (one `gh run list --workflow pitwall-pipeline.yml --limit 1`). Update memory (`lab-state`: version, what's next). Tell Tomas the release URL.
