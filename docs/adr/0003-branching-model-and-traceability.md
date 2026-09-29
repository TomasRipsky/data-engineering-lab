# 0003 — Branching model and traceability

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Tomas wants professional branch management: protected `main`, a stable `dev`, named work branches, and full traceability. The team is two members, one of them an agent acting through Tomas's account.

## Decision
- `main`: released history. `dev`: stable integration. Both protected by GitHub rulesets: PR required, no force-push, no deletion, no bypass (admins included). `dev` allows squash merges only; `main` allows merge commits only.
- Work branches from `dev`: `<type>/<issue#>-<slug>`.
- Chain: issue → branch → Conventional Commits (project scope) → PR with `Closes #n` → squash into `dev` → release PR `dev → main` (merge commit) → tag `vX.Y.Z` + CHANGELOG.
- Required approvals: 0 (GitHub forbids self-approval); required status checks are added when CI exists.
- Repo is public — branch protection on private repos requires a paid plan, and the repo is a portfolio anyway.

## Alternatives considered
- **GitHub Flow (only `main`)** — less overhead; rejected because practising release management is a learning goal.
- **Private repo with local hooks only** — no server-side enforcement.

## Consequences
One extra merge step per release. Clean, reviewable history on `main`. Local `no-commit-to-branch` hook complements server rules.
