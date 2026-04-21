default: just --list

setup: uv sync

lint: uv run ruff check .

fix: uv run ruff check . --fix
  uv run ruff format .

typecheck: uv run mypy src/

test: uv run pytest

coverage: uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=80

audit: uv run pip-audit

build: uv build

check: lint typecheck test audit
