#!/usr/bin/env bash
# Regression tests for reviewer-bash-allowlist.sh. Run: bash .claude/hooks/reviewer-bash-allowlist.test.sh
HOOK="$(dirname "$0")/reviewer-bash-allowlist.sh"
fail=0
check() { # $1 expected (allow|deny), $2 command
  jq -n --arg c "$2" '{tool_input:{command:$c}}' | "$HOOK" >/dev/null 2>&1
  local rc=$?; local got=deny; [[ $rc -eq 0 ]] && got=allow
  [[ $got == "$1" ]] || { echo "FAIL: expected $1, got $got (rc=$rc): $2"; fail=1; }
}
# allowed: inspection
check allow 'git diff dev...HEAD'
check allow 'git log --oneline -5'
check allow 'gh pr diff 11'
check allow 'gh pr view 11 --json headRefOid -q .headRefOid'
check allow 'git diff dev...HEAD | head -50'
check allow 'cd "projects/ais-stream" && make test'
check allow 'uv run --frozen pytest -q 2>&1 | tail -5'
check allow 'ruff check . && ruff format --check .'
check allow 'rg -n "select \*" projects'
check allow 'find projects -name "*.sql"'
# denied: writes, publishing, smuggling
check deny 'git push origin HEAD'
check deny 'gh pr merge 11 --squash'
check deny 'gh pr comment 11 -b hi'
check deny 'git diff > out.patch'
check deny 'git log; rm -rf projects'
check deny 'echo $(gh pr merge 11)'
check deny 'ruff check --fix .'
check deny 'find . -name x -delete'
check deny 'terraform apply -auto-approve'
check deny 'git checkout -b x'
[[ $fail -eq 0 ]] && echo "all allowlist tests passed"
exit $fail
