# 0002 — Python tooling: uv, ruff, pytest

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Every project needs reproducible environments, linting and tests with minimal setup friction.

## Decision
`uv` manages Python versions, virtualenvs, dependencies and lockfiles (build backend `uv_build`). `ruff` lints and formats. `pytest` tests. Configuration lives in each project's `pyproject.toml`.

## Alternatives considered
- **pip + venv + requirements.txt** — no lockfile resolution, slower, more manual steps.
- **Poetry** — mature, but slower and a second tool when uv covers it.
- **black + flake8 + isort** — three tools where ruff is one, 10–100× faster.

## Consequences
One-command setup (`uv sync`). Tomas learns the tooling the industry is converging on. uv is young: pin its build backend to a minor range.
