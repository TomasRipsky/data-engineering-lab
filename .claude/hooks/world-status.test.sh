#!/usr/bin/env bash
# Regression tests for world-status.sh. Run: bash .claude/hooks/world-status.test.sh
HOOK="$(cd "$(dirname "$0")" && pwd)/world-status.sh"
STUB=$(mktemp -d); trap 'rm -rf "$STUB"' EXIT
fail=0
run() { # $1 gh stub body ("" = no gh on PATH); prints output, sets rc and secs
  rm -f "$STUB/gh"
  [[ -n $1 ]] && { printf '#!/usr/bin/env bash\n%s\n' "$1" > "$STUB/gh"; chmod +x "$STUB/gh"; }
  local start=$SECONDS
  out=$(PATH="$STUB:/usr/bin:/bin" CLAUDE_PROJECT_DIR="$PWD" "$HOOK" 2>&1); rc=$?
  secs=$((SECONDS - start))
}
expect() { eval "$2" || { echo "FAIL [$1]: $3"; echo "$out" | sed 's/^/    /'; fail=1; }; }  # $2 is a shell condition

# gh answers: every line present
run 'case "$1 $2" in "issue list") echo "#34 Lab 1.0 (B)";; "pr list") echo "#35 feat";; "run list") echo "completed/success 2026-09-28";; esac'
expect online '[[ $rc -eq 0 ]]' "exit $rc"
for k in "branch:" "issues: #34" "PRs: #35" "pipeline (pitwall, last run): completed/success"; do
  expect online 'grep -qF -- "$k" <<<"$out"' "missing '$k'"
done

# gh fails (offline / unauthenticated): branch line only, no error text, exit 0
run 'echo "error connecting to api.github.com" >&2; exit 1'
expect offline '[[ $rc -eq 0 ]]' "exit $rc"
expect offline 'grep -qF "branch:" <<<"$out"' "missing branch line"
expect offline '! grep -qi error <<<"$out"' "error text leaked"

# no gh on PATH: same as offline
run ''
expect no-gh '[[ $rc -eq 0 ]]' "exit $rc"
expect no-gh 'grep -qF "branch:" <<<"$out"' "missing branch line"
expect no-gh '! grep -q "issues:" <<<"$out"' "printed issues without gh"

# gh hangs: the per-call timeout keeps the hook fast
run 'sleep 30'
expect hang '[[ $rc -eq 0 ]]' "exit $rc"
expect hang '[[ $secs -lt 10 ]]' "took ${secs}s"

[[ $fail -eq 0 ]] && echo "all world-status tests passed"
exit $fail
