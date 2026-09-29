.PHONY: setup test lint fmt destroy

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

destroy: ## Tear down every cloud resource this project creates (implement before first deploy)
	@echo "No cloud resources defined for this project."
