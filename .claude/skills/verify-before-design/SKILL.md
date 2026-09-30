---
name: verify-before-design
description: Checklist to run before designing or planning anything that touches cloud accounts, billing, authentication, CI/CD, or specific tool/library versions — so the spec rests on verified facts, not memory. Use at the start of brainstorming for a new project or cloud feature, and before writing a plan that pins versions or auth modes.
---

# Verify before design

Every item below cost us rework in pitwall because I assumed instead of checking. Verify each one that applies, then paste a **Verified facts** block into the spec.

## Checklist

| # | Fact | How to verify | The pitwall miss it prevents |
|---|---|---|---|
| 1 | **Account and parent** — which org/account, where new projects must live | `gcloud organizations list`, `gcloud projects describe <p> --format='value(parent)'` (AWS: `aws organizations describe-organization`); memory `reference-gcp-account` | Projects first created outside the org |
| 2 | **Billing currency and budget units** | `gcloud billing accounts describe <id>` (`currencyCode`); budgets are set in that currency | A budget written in USD on a EUR account |
| 3 | **Auth modes each tool supports** vs our constraint (keyless: WIF/OIDC/ADC, no long-lived keys) | The tool's current auth docs (Context7 / official), not a blog post | Evidence's current line only takes a BigQuery key → dashboard redesign (pitwall ADR 0007) |
| 4 | **Versions and tags that exist today** for every action, image, package and provider we pin | `gh api repos/<owner>/<repo>/tags --jq '.[0:5][].name'`, `gh release view -R <owner>/<repo>`, PyPI/npm pages, Context7 | `setup-uv` stopped publishing major tags (`@v8` did not exist) |
| 5 | **Quotas, free-tier limits, API enablement** | Pricing/quota pages; after `gcloud services enable`, allow propagation (retry or `time_sleep` in Terraform) | Free-tier boundaries assumed; first apply racing API enablement |
| 6 | **Org policies** that block keys, public access or regions | `gcloud resource-manager org-policies list --organization <id>` | Key creation blocked by policy, discovered mid-build |

## Output — paste into the spec

```markdown
## Verified facts (YYYY-MM-DD)
- <fact> — source: <command output / doc URL>
```

A fact that could not be verified is written as an **assumption** with the risk if wrong, and gets a task in the plan to check it first.
