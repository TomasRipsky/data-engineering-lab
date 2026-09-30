# Security and cost

This repository is **public**. Everything here is written assuming anyone can read it.

## Secrets

- Secrets never enter the repo. Configuration comes from environment variables; only `.env.example` is committed, and `.gitignore` blocks `.env*`, keys, credentials JSON and `*.tfvars`.
- [gitleaks](https://github.com/gitleaks/gitleaks) scans every commit through pre-commit, alongside `detect-private-key` and a branch guard that rejects commits to `main` and `dev`.
- On any fresh clone or new machine, run `pre-commit install` before the first commit — without it no hook runs.
- Claude never reads or prints `.env` files or credentials. Deny rules in `.claude/settings.json` block the Read tool on the same patterns `.gitignore` blocks (`.env` variants, credentials and service-account JSON, `*.tfvars`, keys); `*.example` files stay readable. Shell commands are not covered by those rules — the rule itself still applies.
- CI authenticates to the cloud with short-lived federated identities (Workload Identity Federation), not long-lived keys; public-facing builds use read-only identities (pitwall ADR 0006, `site/README.md`).

## Cloud cost

- **Free tier first.** Choose services and sizes that fit the free tier unless there is a stated reason.
- **Budget alert before the first deploy** of any billable project.
- **Say the expected cost first:** Claude states the expected monthly cost before creating billable resources and waits for Tomas's OK.
- **Teardown is part of the build:** `make destroy` is implemented and tested before anything is left running. Regenerable storage is force-destroyed so teardown never stalls on non-empty buckets or datasets (pitwall ADR 0005).
- Guard unbounded spend: query quotas, partition filters, lifecycle rules, no always-on compute without a reason.
