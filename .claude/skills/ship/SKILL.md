---
name: ship
description: Take the current work branch from committed, verified changes to merged into dev — PR with Closes #n, CI, pr-reviewer, fixes, squash merge, issue closed, branch cleaned, memory updated. Use when a planned change is committed and verified locally and should land in dev.
---

# Ship

**Every bash block below is self-contained:** shell variables do not survive between tool calls, so each block derives `ISSUE`/`PR` again. Never carry a value from an earlier block.

Merge authority (CLAUDE.md): I squash-merge into `dev` once CI is green and review is clean. Releases and PRs into `main` are not shipped here — they go through `/release`, which Tomas runs.

## 1. Preconditions
```bash
BRANCH=$(git branch --show-current)
ISSUE=$(sed -nE 's#^(feat|fix|docs|refactor|test|chore|ci|infra)/([0-9]+)-.*#\2#p' <<<"$BRANCH")  # portable: bash and zsh
: "${ISSUE:?not a work branch: $BRANCH}"
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

## 3. Check the issue link (early warning)
Right after `gh pr create`, GitHub may not have computed the link yet — a "not linked" here can be a false negative. Re-run in a minute; step 6 enforces it as a gate.

GitHub only links `Closes #n` for PRs into the repository's **default** branch. In a repo whose default is `main` while work merges into `dev` (e.g. CityPulse) the link never appears, so there the check reads the body instead, and step 6 closes the issue explicitly after the merge.
```bash
ISSUE=$(git branch --show-current | sed -nE 's#^[a-z]+/([0-9]+)-.*#\1#p'); : "${ISSUE:?not a work branch}"
PR=$(gh pr view --json number -q .number); : "${PR:?no PR for this branch}"
DEFAULT=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name); : "${DEFAULT:?cannot read the default branch}"
if [[ "$DEFAULT" == dev ]]; then
  gh pr view "$PR" --json closingIssuesReferences -q '.closingIssuesReferences[].number' | grep -qx "$ISSUE" \
    && echo "issue #$ISSUE linked to PR #$PR" \
    || echo "STOP: issue #$ISSUE not linked — put 'Closes #$ISSUE' on its own line in the body and re-check"
else
  gh pr view "$PR" --json body -q .body | grep -qx "Closes #$ISSUE" \
    && echo "body says Closes #$ISSUE (no link possible: default branch is $DEFAULT)" \
    || echo "STOP: the body lacks a 'Closes #$ISSUE' line"
fi
```

## 4. CI
Read the app's PR status (`get_status`) when the tool exists, otherwise one `gh pr checks`. Never poll in a loop, sleep, or schedule checks: if checks are pending, end the turn and resume on the CI event or when Tomas says so. A failing check → systematic debugging, fix, push, re-read status. Workflows are path-filtered: a PR that touches no project may report **no checks at all** — then the local gates of step 1 are the CI, and nothing will arrive to wait for.

## 5. Review
Non-trivial change (pipeline, SQL model, infra, dependency, workflow, hook, skill) → run the `pr-reviewer` agent on the branch with the plan's Review Focus. Then:
- Verify its claims before acting — findings are hypotheses.
- Re-grade by effect on the person using the result, not by the reviewer's label.
- Fix Critical/Important with a check that fails first, then passes; push; re-read CI.
- Anything declined is a ruling with its cost-if-wrong, reported to Tomas.

## 6. Merge and close the issue
Gates, in order: base is `dev` → issue linked (or, when `dev` is not the default branch, named in the body) → checks not pending → checks not failing → head unchanged since review. One block, so `ISSUE` and `PR` are still known after the branch is deleted:
```bash
ISSUE=$(git branch --show-current | sed -nE 's#^[a-z]+/([0-9]+)-.*#\1#p'); : "${ISSUE:?not a work branch}"
PR=$(gh pr view --json number -q .number); : "${PR:?no PR for this branch}"
DEFAULT=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name); : "${DEFAULT:?cannot read the default branch}"
BASE=$(gh pr view "$PR" --json baseRefName -q .baseRefName)
gh pr checks "$PR" >/dev/null 2>&1; rc=$?   # 0 = all passed, 8 = pending, other = failed or none reported
if [[ "$BASE" != dev ]]; then
  echo "STOP: PR #$PR targets '$BASE', not dev — ship never merges into main (that is /release)"
elif [[ "$DEFAULT" == dev ]] && ! gh pr view "$PR" --json closingIssuesReferences -q '.closingIssuesReferences[].number' | grep -qx "$ISSUE"; then
  echo "STOP: issue #$ISSUE not linked to PR #$PR (fix the body; re-run in a minute if the PR is brand new)"
elif [[ "$DEFAULT" != dev ]] && ! gh pr view "$PR" --json body -q .body | grep -qx "Closes #$ISSUE"; then
  echo "STOP: the body of PR #$PR lacks a 'Closes #$ISSUE' line"
elif [[ $rc -eq 8 ]]; then echo "STOP: checks pending"
elif [[ $rc -ne 0 ]] && ! gh pr checks "$PR" 2>&1 | grep -q "no checks reported"; then echo "STOP: checks failing"
elif gh pr merge "$PR" --squash --delete-branch --match-head-commit "$(git rev-parse HEAD)"; then
  git switch dev && git pull --ff-only      # gh may leave local dev behind
  [[ "$(gh issue view "$ISSUE" --json state -q .state)" == CLOSED ]] \
    || gh issue close "$ISSUE" --comment "Delivered by #$PR."
  echo "merged PR #$PR; issue #$ISSUE: $(gh issue view "$ISSUE" --json state -q .state)"
fi
```
- `--match-head-commit` refuses the merge if anything was pushed after the review.
- "no checks reported" passes only because step 4 established that no workflow applies.
- GitHub registers the link but does not always close the issue on merge into `dev` (cause unknown — `agent/lessons.md`), hence the explicit check. When `dev` is not the default branch there is no link at all, and the explicit close (if the issue is still open) is what delivers it.

## 7. Record and report
- Update memory (`lab-state`) if the project state changed.
- If a lesson surfaced, apply it now (`agent/lessons.md` + `agent/CHANGELOG.md`).
- Tell Tomas: PR link, merge commit, issue state, rulings and deferred minors.
