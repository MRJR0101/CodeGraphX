# Python Project "Definition of Done" Checklist

> A project is "complete" when someone (including future-you) can clone it,
> set it up in one command, understand it, test it, lint it, audit it, and ship it.

---

## 1. Project Structure

- [ ] Uses `src/` layout (`src/packagename/`) -- not flat modules in root
- [ ] Has a `pyproject.toml` as the single source of project metadata
- [ ] Has a `README.md` with: purpose, install steps, usage examples, config options
- [ ] Has a `CHANGELOG.md` or release notes (even if just "v1.0 - initial release")
- [ ] Has a `LICENSE` file (MIT, Apache-2.0, or your preference)
- [ ] Has a `.gitignore` tuned for Python (caches, venvs, build artifacts, .env)
- [ ] No secrets, API keys, or credentials committed (check git history too)
- [ ] Entry points defined in `pyproject.toml` (`[project.scripts]` or `[project.gui-scripts]`)

## 2. Dependency Management (uv)

- [ ] All dependencies declared in `pyproject.toml` under `[project.dependencies]`
- [ ] Dev dependencies separated in `[project.optional-dependencies]` or `[dependency-groups]`
- [ ] Lock file committed (`uv.lock`) for reproducible installs
- [ ] `uv sync` from a fresh clone produces a working environment
- [ ] No pinned deps in source that conflict with lock (let uv handle resolution)
- [ ] Python version constraint set (`requires-python = ">=3.11"` or your minimum)

## 3. Code Quality -- Linting and Formatting

- [ ] Ruff configured in `pyproject.toml` under `[tool.ruff]`
- [ ] Rule sets enabled: at minimum `E`, `F`, `W`, `I` (errors, pyflakes, warnings, isort)
- [ ] Consider also: `UP` (pyupgrade), `S` (bandit/security), `B` (bugbear), `SIM` (simplify)
- [ ] `ruff check .` passes with zero errors
- [ ] `ruff format .` produces no changes (code is already formatted)
- [ ] Line length configured (88 or 120, pick one, be consistent)

## 4. Type Checking

- [ ] Type hints on all public functions and class methods
- [ ] `mypy` configured in `pyproject.toml` under `[tool.mypy]`
- [ ] `mypy src/` passes (or has a clear, shrinking ignore list)
- [ ] `py.typed` marker file present if distributing as a typed package

## 5. Testing

- [ ] `tests/` directory with meaningful test coverage
- [ ] `pytest` configured in `pyproject.toml` under `[tool.pytest.ini_options]`
- [ ] `pytest-cov` installed for coverage measurement
- [ ] `uv run pytest` passes from a clean environment
- [ ] `uv run pytest --cov=src --cov-report=term-missing` reports coverage
- [ ] Coverage target set (aim for 80%+ on core logic, don't chase 100% on glue code)
- [ ] Tests are independent (no test depends on another test's side effects)
- [ ] Fixtures and mocks used for external dependencies (APIs, databases, filesystem)
- [ ] Tests pass on both Linux and Windows (no hardcoded `/` paths or Unix assumptions)

## 6. Pre-commit Hooks

- [ ] `.pre-commit-config.yaml` present in repo root
- [ ] Hooks include at minimum: ruff (lint + format), mypy, trailing whitespace, end-of-file fixer
- [ ] `pre-commit run --all-files` passes cleanly
- [ ] Contributors doc mentions running `pre-commit install` after clone

## 7. CI/CD (GitHub Actions)

- [ ] Workflow file at `.github/workflows/ci.yml`
- [ ] Triggers on push to main and all pull requests
- [ ] Matrix tests across target Python versions (e.g., 3.11, 3.12, 3.13)
- [ ] Cross-platform matrix includes `windows-latest` (at minimum for one Python version)
- [ ] Steps: install uv, sync deps, lint, typecheck, test, security audit
- [ ] Fails the build on any lint error, type error, test failure, or known vulnerability
- [ ] Badge in README showing CI status

## 8. Security

- [ ] `pip-audit` runs clean against the locked dependencies
- [ ] No known CVEs in dependency tree
- [ ] SBOM generated (CycloneDX JSON) -- even if just stored as CI artifact
- [ ] Secrets managed via environment variables, never hardcoded
- [ ] `.env.example` file shows required env vars (without real values)
- [ ] If accepting user input: input validation and sanitization present

## 9. Automated Dependency Updates

- [ ] Dependabot or Renovate configured for the repo
- [ ] Update schedule set (weekly is a good default, daily for security-sensitive projects)
- [ ] Automerge enabled for patch-level updates that pass CI
- [ ] Update PRs are reviewed and merged regularly (not left to rot)
- [ ] Config file committed: `.github/dependabot.yml` or `renovate.json`

## 10. Coverage Reporting

- [ ] `pytest-cov` in dev dependencies
- [ ] Coverage configured in `pyproject.toml` under `[tool.coverage.run]`
- [ ] Source set to `src/` to measure only your code (not tests or venv)
- [ ] `uv run pytest --cov=src --cov-report=term-missing` shows current coverage
- [ ] Coverage report uploaded as CI artifact (or to Codecov/Coveralls)
- [ ] Minimum coverage threshold enforced in CI (`--cov-fail-under=80`)
- [ ] Branch coverage enabled (`branch = true`) for meaningful metrics

## 11. Task Runner

- [ ] `justfile` or `Makefile` present in repo root
- [ ] Common commands wrapped: lint, format, test, typecheck, audit, build, clean
- [ ] `just --list` (or `make help`) shows available commands
- [ ] New contributor can run `just setup` (or equivalent) to bootstrap environment
- [ ] Commands use `uv run` under the hood (not bare `python` or `pip`)

## 12. Documentation

- [ ] All public modules have docstrings (module-level)
- [ ] All public functions/classes have docstrings (Google or NumPy style, pick one)
- [ ] Complex logic has inline comments explaining *why*, not *what*
- [ ] Configuration options documented (CLI flags, env vars, config file format)
- [ ] If library: API reference docs (even if just well-structured docstrings)

## 13. Packaging and Distribution

- [ ] `pyproject.toml` has correct metadata: name, version, description, author, URLs
- [ ] Version managed in one place (pyproject.toml or `__version__` with single-source)
- [ ] `uv build` produces a working wheel and sdist
- [ ] Package installs cleanly via `uv pip install dist/*.whl`
- [ ] If publishing to PyPI: `[build-system]` configured (hatchling, setuptools, or flit)

## 14. Git Hygiene

- [ ] Main branch is protected (no direct pushes in team repos)
- [ ] Commits are atomic and messages are descriptive
- [ ] No large binary files committed (use `.gitattributes` or Git LFS if needed)
- [ ] Tags for releases (`v1.0.0`, `v1.1.0`, etc.)
- [ ] Stale branches cleaned up

## 15. Contributing and Collaboration (team/public projects)

- [ ] `CONTRIBUTING.md` with setup steps, code standards, and PR process
- [ ] GitHub issue templates (bug report, feature request)
- [ ] GitHub PR template with checklist (tests pass, lint clean, docs updated)
- [ ] Release workflow: tag push triggers build + publish to PyPI (if applicable)
- [ ] Changelog auto-generated from commits or PR labels

---

## Quick Start for Restoring an Existing Project

Priority order when bringing a messy project up to "done":

```
1. Get it running        --> uv init / uv sync / fix imports
2. Lock dependencies     --> uv lock (commit uv.lock)
3. Add pyproject.toml    --> migrate setup.py/setup.cfg/requirements.txt
4. Add ruff              --> fix lint errors (auto-fix most with ruff check --fix)
5. Add basic tests       --> even just smoke tests that import and run
6. Add coverage          --> pytest-cov, know where you stand
7. Add pre-commit        --> prevent regression
8. Add justfile          --> wrap common commands, reduce friction
9. Add CI                --> automate everything above (test on Windows too)
10. Add pip-audit        --> catch vulnerable deps
11. Add Dependabot       --> keep deps fresh automatically
12. Add type hints       --> gradual, start with public API
13. Add docs/README      --> future-you will thank present-you
```

Each step is independently valuable. A project at step 5 is vastly better
than one at step 0, even if it never reaches step 10.

---

## Minimal pyproject.toml Reference

```toml
[project]
name = "my-tool"
version = "1.0.0"
description = "What this tool does in one line"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=6.0",
    "ruff>=0.8",
    "mypy>=1.13",
    "pip-audit>=2.7",
    "pre-commit>=4.0",
]

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "S", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

---

## Minimal justfile Reference

```just
# justfile -- run `just` to see all commands

default:
    @just --list

# Bootstrap environment from scratch
setup:
    uv sync

# Run linter
lint:
    uv run ruff check .

# Auto-fix lint errors
fix:
    uv run ruff check . --fix
    uv run ruff format .

# Run type checker
typecheck:
    uv run mypy src/

# Run tests with coverage
test:
    uv run pytest

# Run security audit
audit:
    uv run pip-audit

# Build package
build:
    uv build

# Run all checks (what CI does)
check: lint typecheck test audit
```

---

## Minimal .github/dependabot.yml Reference

```yaml
version: 2
updates:
  # Python dependencies via pip (reads pyproject.toml)
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10

  # GitHub Actions versions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
```
