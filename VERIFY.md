# Verification Guide

This file documents the current validation path for the repository. It is a
guide for contributors, not a frozen snapshot of one machine's file counts or
internal report output.

## Last Local Verification

Validated on 2026-03-08 with the canonical package under `src/codegraphx`.

Current expected quick-check results:

- `python -m pytest -q` passes
- `python -m codegraphx --help` exits successfully
- `python cli/main.py --version` prints the packaged version when dependencies are installed

## Fast Validation

Run these for most changes:

```bash
python -m pytest -q
python -m codegraphx --help
```

## Windows No-DB Smoke

This exercises the JSONL-first pipeline without requiring Neo4j:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_no_db.ps1 -ReportPath smoke_no_db_report.json
```

The report file is local output and should not be committed.

## Full Release Gate

The full scripted gate requires `uv`:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

That gate runs project checks, linting, typing, tests, package build, and the
no-database smoke test.

## Optional Neo4j Validation

For changes that affect graph loading, Cypher, or `doctor` behavior:

1. Copy `.env.example` to `.env` and fill in credentials.
2. Start Neo4j -- Docker is the easiest path:
   ```powershell
   .\start-neo4j.ps1
   ```
3. Run `python -m codegraphx doctor`.
4. Run `python -m codegraphx load` against a generated `events.jsonl`.
5. Confirm `data/search.db` is created and `search` returns results.

## Artifact Expectations

Expected local artifacts during validation include:

- `data/*.jsonl`
- `data/*.json`
- `smoke_no_db_report.json`
- `.pytest_tmp/`

These are local outputs and should stay ignored unless a fixture explicitly
needs them.
