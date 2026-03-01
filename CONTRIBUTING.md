# Contributing to codegraphx

Thank you for contributing to CodeGraphX. Keep changes reproducible, configuration-driven, and easy to validate in CI.

## Development Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Coding Standards

- Prefer typed functions and explicit return types for public APIs.
- Keep CLI behavior backward-compatible unless a documented breaking change is required.
- Route new runtime toggles through YAML/config or explicit CLI options.
- Avoid hidden side effects in pipeline stages; deterministic outputs are required.
- Update docs when commands, flags, or output artifacts change.

## Testing

Run before opening a PR:

```bash
python -m pytest -q
powershell -ExecutionPolicy RemoteSigned -File .\scripts\smoke_no_db.ps1 -ReportPath smoke_no_db_report.json
```

If your change affects graph loading, also validate Neo4j-backed flows in your environment.

## Pull Request Checklist

- [ ] Tests pass locally.
- [ ] CLI help and README examples are updated for command/flag changes.
- [ ] Config defaults and migration implications are documented.
- [ ] New artifacts are deterministic and safe to diff.

## Documentation Requirements

For user-visible behavior changes, update:

- `README.md`
- `VERIFY.md`
- `CHANGELOG.md`

