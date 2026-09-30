#!/usr/bin/env bash
# SessionStart hook: a short "state of the world" added to Claude's context (stdout on exit 0).
# Never fails, never blocks: every gh call has a timeout and any failure just ends the report.
set -u
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
# 5 s per call (macOS has no `timeout`). The call runs in its own process group and the whole group is
# killed on timeout: killing only gh would leave children holding stdout open, and $(...) would wait.
t() { perl -e 'my $s = shift; my $pid = fork // exit 1;
  if (!$pid) { setpgrp; exec @ARGV or exit 127 }
  $SIG{ALRM} = sub { kill "KILL", -$pid; exit 124 }; alarm $s; waitpid $pid, 0; exit($? >> 8)' 5 "$@" 2>/dev/null; }

echo "World status ($(date -u +%F)):"
echo "- branch: $(git branch --show-current 2>/dev/null || echo '?')"
command -v gh >/dev/null || exit 0
issues=$(t gh issue list --state open --limit 10 --json number,title -q '.[] | "#\(.number) \(.title)"') || exit 0
prs=$(t gh pr list --state open --limit 10 --json number,title -q '.[] | "#\(.number) \(.title)"') || exit 0
run=$(t gh run list --workflow pitwall-pipeline.yml --limit 1 --json status,conclusion,createdAt \
  -q '.[0] | "\(.status)/\(.conclusion // "-") \(.createdAt[:10])"') || run="?"
echo "- issues: $(paste -sd ';' - <<<"${issues:-none}")"
echo "- PRs: $(paste -sd ';' - <<<"${prs:-none}")"
echo "- pipeline (pitwall, last run): ${run:-none}"
exit 0
