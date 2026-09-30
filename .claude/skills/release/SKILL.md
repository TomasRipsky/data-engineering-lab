---
name: release
description: Cut a lab release vX.Y.Z — changelogs, PR dev → main with a merge commit, GitHub release.
disable-model-invocation: true
argument-hint: "[X.Y.Z]"
---

# Release v$ARGUMENTS

This skill only runs when Tomas types `/release X.Y.Z` — that is his explicit OK to merge `dev` into `main`. The GitHub release itself is public, so I still show him the notes before creating it.

## 1. Validate
```bash
V="$ARGUMENTS"
[[ "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "not SemVer: $V"; exit 1; }
git switch dev && git pull --ff-only
gh release view "v$V" >/dev/null 2>&1 && { echo "v$V already exists"; exit 1; }
awk '/^## \[Unreleased\]/{f=1;next}/^## \[/{f=0}f' CHANGELOG.md | grep -q '[^[:space:]]' || { echo "[Unreleased] is empty"; exit 1; }
```
Check SemVer against the changes: breaking or structural → major; features → minor; fixes → patch. If `$V` looks wrong, say so before continuing.

## 2. Changelog PR into dev
```bash
URL=$(gh issue create --title "chore(lab): release v$V" --label type:chore --label project:lab --body "Release v$V.")
N=${URL##*/}
git switch -c "chore/$N-release-v$V"
```
In `CHANGELOG.md` and `agent/CHANGELOG.md`: rename `## [Unreleased]` to `## [$V] - <today>` and add a fresh empty `## [Unreleased]` above it. Commit `chore(lab): release v$V`, then follow the `ship` skill (steps 2–7) to land it in `dev`.

## 3. dev → main
```bash
gh pr create --base main --head dev --title "release: v$V" --body-file "$NOTES_FILE"
gh pr merge "$MAIN_PR" --merge    # merge commit, never squash: main keeps release boundaries
```
`$NOTES_FILE` = the `[$V]` sections of both changelogs + attribution line. Wait for CI on the PR before merging.

## 4. GitHub release (public — show Tomas first)
Show Tomas the notes and wait for his OK, then:
```bash
gh release create "v$V" --target main --title "v$V" --notes-file "$NOTES_FILE"
git fetch -q --tags && git diff --quiet origin/main origin/dev -- . && echo "main == dev"
```

## 5. After
Update memory (`lab-state`: version, what's next). Tell Tomas the release URL.
