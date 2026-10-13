# Security and cost

This repository and every project repository are **public**. Everything is written assuming anyone can read it.

## Secrets

- Secrets never enter the repo. Configuration comes from environment variables; only `.env.example` is committed, and `.gitignore` blocks `.env*`, keys, credentials JSON and `*.tfvars`.
- [gitleaks](https://github.com/gitleaks/gitleaks) scans every commit through pre-commit, alongside `detect-private-key` and a branch guard that rejects commits to `main` and `dev`.
- On any fresh clone or new machine, run `pre-commit install` before the first commit — without it no hook runs.
- Claude never reads or prints `.env` files or credentials. Deny rules in `.claude/settings.json` (anchored at the project root, `/**/…`) block the Read tool on the `.gitignore` secret patterns: `.env`, keys and certificates (`*.pem`, `*.key`, `*.p8`, `*.p12`, `*.pfx`), credentials and service-account JSON, `*.tfvars`, `.envrc`, `kubeconfig`, `.databrickscfg`, dbt `profiles.yml`. `.env.*` variants are enumerated (`local`, `prod`, `dev`, `staging`, `test`, `ci`, `backup`, `bak`, `old`) because rule patterns have no negation to spare `.env.example`; an unusual name outside that list is not covered. `*.example` files stay readable. Cloud CLI credentials in the home directory (`~/.config/gcloud`, `~/.aws`, `~/.azure`, `~/.kube`, `~/.databrickscfg`) are denied too. The same patterns are repeated for `~/Data Engineering/Proyectos Data/**`, because project-settings rules are anchored at the lab root and projects live in sibling clones (lab ADR 0007). Shell commands are only partly covered by these rules — the rule itself still applies.
- CI authenticates to the cloud with short-lived federated identities (Workload Identity Federation), not long-lived keys; public-facing builds use read-only identities (pitwall ADR 0006, `template/site/README.md`). The trust is bound to the project repository's **numeric ID**, not its name: moving or recreating a repository means re-applying the infrastructure with the new ID. Terraform state that is kept local lives only in the project's clone — it moves with the clone and is never committed.

## Cloud cost

- **Free tier first.** Choose services and sizes that fit the free tier unless there is a stated reason.
- **Budget alert before the first deploy** of any billable project.
- **Say the expected cost first:** Claude states the expected monthly cost before creating billable resources and waits for Tomas's OK.
- **Teardown is part of the build:** `make destroy` is implemented and tested before anything is left running. Regenerable storage is force-destroyed so teardown never stalls on non-empty buckets or datasets (pitwall ADR 0005).
- Guard unbounded spend: query quotas, partition filters, lifecycle rules, no always-on compute without a reason.
