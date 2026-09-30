---
name: ship
description: Take the current work branch from committed, verified changes to merged into dev — PR with Closes #n, CI, pr-reviewer, fixes, squash merge, issue closed, branch cleaned, memory updated. Use when a planned change is committed and verified locally and should land in dev.
---

# Ship

Merge authority (CLAUDE.md): I squash-merge into `dev` once CI is green and review is clean. Releases and PRs into `main` are not shipped here — they go through `/release`, which Tomas runs.

## 1. Preconditions
```bash
BRANCH=$(git branch --show-current)
ISSUE=$(sed -nE 's#^(feat|fix|docs|refactor|test|chore|ci|infra)/([0-9]+)-.*#\2#p' <<<"$BRANCH")  # portable: bash and zsh
[[ -n "$ISSUE" ]] || { echo "not a work branch: $BRANCH"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "working tree not clean"; exit 1; }
git fetch -q origin dev && git log --oneline origin/dev..HEAD
```
Run the local gates for what changed: `make lint` and `make test` in every touched project, the hook tests if `.claude/hooks/` changed, and a link check if docs moved. Read every output — one purpose per command, no long `&&` chains that hide which step failed.

## 2. Push and open the PR
```bash
git push -u origin HEAD
gh pr create --base dev --title "<conventional title>" --body-file "$BODY_FILE"
```
The body starts with `Closes #$ISSUE`, then a summary, verification results, and ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Write it to a file first (quotes and backticks survive).

## 3. Check the issue link before merging
```bash
PR=$(gh pr view --json number -q .number)
gh pr view "$PR" --json closingIssuesReferences -q '[.closingIssuesReferences[].number]' | grep -qw "$ISSUE" \
  || echo "issue #$ISSUE not linked: fix the body (Closes #$ISSUE on its own line) and re-check"
```

## 4. CI
Read the app's PR status (`get_status`). Never poll in a loop, sleep, or schedule checks: if checks are pending, end the turn and resume on the CI event or when Tomas says so. A failing check → systematic debugging, fix, push, re-read status.

## 5. Review
Non-trivial change (pipeline, SQL model, infra, dependency, workflow, hook, skill) → run the `pr-reviewer` agent on the branch with the plan's Review Focus. Then:
- Verify its claims before acting — findings are hypotheses.
- Re-grade by effect on the person using the result, not by the reviewer's label.
- Fix Critical/Important with a check that fails first, then passes; push; re-read CI.
- Anything declined is a ruling with its cost-if-wrong, reported to Tomas.

## 6. Merge
```bash
gh pr merge "$PR" --squash --delete-branch
git switch dev && git pull --ff-only    # gh may leave local dev behind
```

## 7. Issue closed?
```bash
[[ "$(gh issue view "$ISSUE" --json state -q .state)" == CLOSED ]] \
  || gh issue close "$ISSUE" --comment "Delivered by #$PR."
```
GitHub registers the link but does not always close the issue on merge into `dev` (cause unknown — `agent/lessons.md`).

## 8. Record and report
- Update memory (`lab-state`) if the project state changed.
- If a lesson surfaced, apply it now (`agent/lessons.md` + `agent/CHANGELOG.md`).
- Tell Tomas: PR link, merge commit, issue state, rulings and deferred minors.
