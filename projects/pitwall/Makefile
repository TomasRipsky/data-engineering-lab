.PHONY: setup test lint fmt ingest load transform site-data site site-preview bootstrap init plan apply destroy gh-vars

ENV ?= dev
PROJECT_PREFIX ?= pitwall-tr
# Budget alert amount, in the billing account currency (EUR for this account)
BUDGET_AMOUNT ?= 5
PROJECT_ID := $(PROJECT_PREFIX)-$(ENV)
TF := terraform -chdir=infra/gcp
TF_VARS := -var env=$(ENV) -var project_id=$(PROJECT_ID)

# Override with a local path (e.g. PITWALL_LAKE_URI=.lake) to work offline.
export PITWALL_LAKE_URI ?= gs://$(PROJECT_ID)-raw
export PITWALL_BQ_PROJECT ?= $(PROJECT_ID)

ifeq ($(filter $(ENV),dev prod),)
$(error ENV must be dev or prod, got '$(ENV)')
endif

setup: ## Create the virtualenv and install dependencies
	uv sync

test: ## Run the test suite
	uv run pytest

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Auto-format and auto-fix
	uv run ruff format .
	uv run ruff check --fix .

ingest: ## Pull OpenF1 data into $$PITWALL_LAKE_URI (default .lake/). Usage: make ingest ARGS="--meeting 1255"
	uv run pitwall ingest $(ARGS)

load: ## Rebuild BigQuery raw tables in $(PROJECT_ID) from the lake
	uv run pitwall load

transform/profiles.yml: transform/profiles.yml.example
	cp $< $@

transform: transform/profiles.yml ## Build and test the dbt models in $(PROJECT_ID)
	cd transform && uv run dbt deps --quiet && uv run dbt build --target $(ENV) --profiles-dir .

SITE_DIR := ../../site

site-data: ## Export pitwall's section data from $(PROJECT_ID) marts into the lab site
	uv run pitwall site-export --out $(SITE_DIR)/src/pitwall/data

site: site-data ## Build the whole lab site into site/dist
	cd $(SITE_DIR) && npm ci --silent && npm run build

site-preview: site-data ## Live-reloading lab site on http://127.0.0.1:3000
	cd $(SITE_DIR) && npm ci --silent && npm run dev

bootstrap: ## One-off per env: create project, link billing, budget alert. BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX ORG_ID=XXXXXXXXXXXX
	@test -n "$(BILLING_ACCOUNT)" || { echo "set BILLING_ACCOUNT (see: gcloud billing accounts list)"; exit 1; }
	@test -n "$(ORG_ID)" || { echo "set ORG_ID (see: gcloud organizations list)"; exit 1; }
	gcloud projects create $(PROJECT_ID) --name="pitwall $(ENV)" --organization=$(ORG_ID)
	gcloud billing projects link $(PROJECT_ID) --billing-account=$(BILLING_ACCOUNT)
	gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com billingbudgets.googleapis.com --project=$(PROJECT_ID)
	gcloud billing budgets create --billing-account=$(BILLING_ACCOUNT) --billing-project=$(PROJECT_ID) \
	  --display-name="pitwall-$(ENV)" --budget-amount=$(BUDGET_AMOUNT) --filter-projects=projects/$(PROJECT_ID) \
	  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0

init:
	$(TF) init -input=false
	$(TF) workspace select -or-create $(ENV)

plan: init ## Show infrastructure changes for ENV
	$(TF) plan $(TF_VARS)

apply: init ## Create/update infrastructure for ENV (cost: US$0/month expected)
	$(TF) apply $(TF_VARS)

destroy: init ## Delete every resource Terraform created in ENV (lake data included)
	$(TF) destroy $(TF_VARS)

gh-vars: init ## Publish ENV's project, WIF provider and service account to the GitHub environment ENV
	gh variable set PITWALL_PROJECT --env $(ENV) --body "$(PROJECT_ID)"
	gh variable set PITWALL_WIF_PROVIDER --env $(ENV) --body "$$($(TF) output -raw workload_identity_provider)"
	gh variable set PITWALL_SERVICE_ACCOUNT --env $(ENV) --body "$$($(TF) output -raw pipeline_service_account)"
