#!/usr/bin/env bash
# SessionStart hook: a short "state of the world" added to Claude's context (stdout on exit 0).
# Never fails, never blocks: every gh call has a timeout and any failure just ends the report.
set -u
set -o pipefail  # `gh … | jq …` must fail when gh fails or times out, not only when jq does
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
# 5 s per call (macOS has no `timeout`). The call runs in its own process group and the whole group is
# killed on timeout: killing only gh would leave children holding stdout open, and $(...) would wait.
t() { perl -e 'my $s = shift; my $pid = fork // exit 1;
  if (!$pid) { setpgrp; exec @ARGV or exit 127 }
  $SIG{ALRM} = sub { kill "KILL", -$pid; exit 124 }; alarm $s; waitpid $pid, 0; exit($? & 127 ? 128 + ($? & 127) : $? >> 8)' 5 "$@" 2>/dev/null; }

echo "World status ($(date -u +%F)):"
git rev-parse --git-dir >/dev/null 2>&1 || { echo "- not a git repo"; exit 0; }
echo "- branch: $(git branch --show-current 2>/dev/null | grep . || echo "detached at $(git rev-parse --short HEAD 2>/dev/null)")"
# Skills, hooks and CLAUDE.md load from the checked-out branch: name the rule files dev changed since
# this branch forked (as of the last fetch), so a stale skill is not followed. main lags dev by design;
# agent/CHANGELOG.md and agent/lessons.md are records, not rules.
branch=$(git branch --show-current 2>/dev/null)
if [[ $branch != main ]]; then
  stale=$(git diff --name-only HEAD...origin/dev -- .claude CLAUDE.md agent \
    ':!agent/CHANGELOG.md' ':!agent/lessons.md' 2>/dev/null)
  if [[ -n $stale ]]; then
    n=$(wc -l <<<"$stale"); list=$(head -8 <<<"$stale" | paste -sd ' ' -)
    (( n > 8 )) && list+=" (+$((n - 8)) more)"
    fix="merge dev in"; [[ $branch == dev ]] && fix="git pull --ff-only"
    echo "- stale rules: origin/dev changed $list since this branch forked — read those from origin/dev or $fix"
  fi
fi
command -v gh >/dev/null || exit 0
# Public repo: anyone can open issues/PRs, so only the owner's titles enter Claude's context; others are counted.
owner=$(t gh repo view --json owner -q .owner.login) || exit 0
fmt='[.[] | select(.author.login == $o) | "#\(.number) \(.title)"] + ([.[] | select(.author.login != $o)] | if length > 0 then ["+\(length) by others (titles hidden)"] else [] end) | .[]'
issues=$(t gh issue list --state open --limit 20 --json number,title,author | jq -r --arg o "$owner" "$fmt") || exit 0
prs=$(t gh pr list --state open --limit 20 --json number,title,author | jq -r --arg o "$owner" "$fmt") || exit 0
echo "- issues: $(paste -sd ';' - <<<"${issues:-none}")"
echo "- PRs: $(paste -sd ';' - <<<"${prs:-none}")"
# One repository per project (lab ADR 0007): the README's Projects table is the registry. Only the
# owner's repositories are queried, with the same owner-only rule for titles. The last run counts only
# events a stranger cannot cause (push, schedule, manual): a fork's pull request can name a workflow.
# The first call that fails or times out ends the report, so a hanging gh costs one timeout, not nine.
runfmt='[.[] | select(.event == "push" or .event == "schedule" or .event == "workflow_dispatch")][0] // empty
  | "\(.workflowName) \(.status)/\(.conclusion // "-") \(.createdAt[:10])"'
for repo in $(awk '/^## Projects/{f=1;next} /^## /{f=0} f && /^\|/' README.md 2>/dev/null \
    | grep -oE 'github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' | sed 's#^github\.com/##' | awk '!seen[$0]++'); do
  [[ ${repo%%/*} == "$owner" ]] || continue
  pi=$(t gh issue list -R "$repo" --state open --limit 20 --json number,title,author | jq -r --arg o "$owner" "$fmt") \
    && pp=$(t gh pr list -R "$repo" --state open --limit 20 --json number,title,author | jq -r --arg o "$owner" "$fmt") \
    && pr=$(t gh run list -R "$repo" --limit 20 --json workflowName,status,conclusion,createdAt,event | jq -r "$runfmt") \
    || { echo "- ${repo#*/}: unavailable"; break; }
  echo "- ${repo#*/}: issues: $(paste -sd ';' - <<<"${pi:-none}") · PRs: $(paste -sd ';' - <<<"${pp:-none}") · last run: ${pr:-none}"
done
exit 0
