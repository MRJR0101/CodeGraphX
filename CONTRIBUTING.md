# Contributing to CodeGraphX

Keep changes deterministic, config-driven, and easy to validate from a clean clone.

## Setup

Choose one workflow:

```bash
# pip
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate   # Linux/macOS
pip install -e ".[dev]"

# or uv
uv sync --all-groups
```

Sanity-check the install before editing:

```bash
python -m codegraphx --help
python -m pytest -q
```

## Working Rules

- Make changes in the canonical package under `src/codegraphx`.
- Preserve deterministic pipeline behavior and stable artifact naming.
- Route new runtime toggles through config files or explicit CLI options.
- Keep user-facing CLI behavior backward-compatible unless a breaking change is deliberate and documented.
- Update docs when commands, flags, config defaults, or emitted artifacts change.

## Generated Files

Do not commit local-only artifacts such as:

- `config/projects.yaml`
- `config/projects.local.yaml`
- `data/`
- smoke reports, audit summaries, or temporary ledgers
- virtual environments, caches, and build output

If you add a new generated artifact, either document why it belongs in the repo or add it to `.gitignore`.

## Validation

Run the fast path for most changes:

```bash
python -m pytest -q
python -m codegraphx --help
```

For Windows no-DB validation:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_no_db.ps1 -ReportPath smoke_no_db_report.json
```

For the full gate, install `uv` and run:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

If your change affects Neo4j loading or Cypher behavior, also validate against a real Neo4j instance.

## Pull Request Checklist

- [ ] Tests pass locally.
- [ ] CLI help, README examples, and docs match the implemented behavior.
- [ ] Dependency changes are reflected in `pyproject.toml`, `setup.py`, and `requirements.txt`.
- [ ] Config changes are reflected in `.env.example` or example YAML files where relevant.
- [ ] New artifacts are deterministic and safe to diff.

## Files To Update When Behavior Changes

- `README.md` for user-facing usage changes
- `docs/` for deeper command or architecture changes
- `CHANGELOG.md` for releasable changes
- `VERIFY.md` when the recommended validation flow changes

