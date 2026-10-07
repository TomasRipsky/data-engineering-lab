#!/usr/bin/env bash
# SessionStart hook: a short "state of the world" added to Claude's context (stdout on exit 0).
# Never fails, never blocks: every gh call has a timeout and any failure just ends the report.
set -u
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
run=$(t gh run list --workflow pitwall-pipeline.yml --limit 1 --json status,conclusion,createdAt \
  -q '.[0] | "\(.status)/\(.conclusion // "-") \(.createdAt[:10])"') || run="?"
echo "- issues: $(paste -sd ';' - <<<"${issues:-none}")"
echo "- PRs: $(paste -sd ';' - <<<"${prs:-none}")"
echo "- pipeline (pitwall, last run): ${run:-none}"
exit 0
