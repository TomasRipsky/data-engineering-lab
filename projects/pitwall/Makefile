.PHONY: setup test lint fmt ingest load bootstrap init plan apply destroy

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

bootstrap: ## One-off per env: create project, link billing, budget alert. BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX ORG_ID=651783965785
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
