.PHONY: setup test lint fmt ingest destroy

export PITWALL_LAKE_URI ?= .lake

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

destroy: ## Tear down every cloud resource this project creates (implement before first deploy)
	@echo "No cloud resources defined for this project."
