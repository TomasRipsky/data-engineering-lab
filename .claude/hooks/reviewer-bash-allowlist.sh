#!/usr/bin/env bash
# PreToolUse hook for the pr-reviewer agent: only inspection commands may run.
# Fail-closed: anything not on the allowlist (or not safely parseable) is blocked with exit 2.
cmd=$(jq -r '.tool_input.command // empty')
deny() { echo "pr-reviewer is read-only; blocked: $1" >&2; exit 2; }

[[ -z $cmd ]] && deny "empty command"
[[ $cmd == *'$('* || $cmd == *'`'* ]] && deny "command substitution"
stripped=${cmd//2>&1/}; stripped=${stripped//2>\/dev\/null/}; stripped=${stripped//>\/dev\/null/}
[[ $stripped == *'>'* ]] && deny "output redirection"
[[ $cmd =~ (--fix|-delete|-exec|-ok) ]] && deny "mutating flag"

while IFS= read -r seg; do
  seg=$(sed -E 's/^[[:space:]]+|[[:space:]]+$//g' <<<"$seg")
  [[ -z $seg ]] && continue
  [[ $seg =~ ^(cd|rg|grep|head|tail|wc|sort|uniq|jq|cat|ls|find)([[:space:]]|$) ]] && continue
  [[ $seg =~ ^git[[:space:]]+(diff|log|show|status|rev-parse|ls-files|blame)([[:space:]]|$) ]] && continue
  [[ $seg =~ ^gh[[:space:]]+(pr[[:space:]]+(view|diff|checks)|issue[[:space:]]+view)([[:space:]]|$) ]] && continue
  [[ $seg =~ ^make[[:space:]]+(test|lint)$ ]] && continue
  [[ $seg =~ ^uv[[:space:]]+run[[:space:]]+--frozen[[:space:]]+(pytest|ruff[[:space:]]+check|ruff[[:space:]]+format[[:space:]]+--check)([[:space:]]|$) ]] && continue
  [[ $seg =~ ^ruff[[:space:]]+(check|format[[:space:]]+--check)([[:space:]]|$) ]] && continue
  deny "$seg"
done < <(sed -E 's/(&&|\|\||;|\|)/\n/g' <<<"$cmd")
exit 0
