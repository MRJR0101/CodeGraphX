# codegraphx

Tree-sitter → semantic facts → graph database → analysis (duplicates, patterns) → (later) LLM NL interface.

## Compatibility

- Python: 3.10 to 3.13
- Neo4j: 5.x (for `load` and graph-backed analysis)
- OS: Windows and Linux (CI-covered)

## Quick start (dev)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
codegraphx --help
```

## Typical flow (MVP)

1. Copy `config/projects.example.yaml` to `config/projects.yaml` and set project roots.
2. Run:

```bash
codegraphx scan
codegraphx parse
codegraphx extract
codegraphx load --backend neo4j
codegraphx analyze duplicates
```

This scaffold is intentionally minimal; each stage writes deterministic JSONL "graph events"
so you can replay/inspect the facts before touching the DB.

## No-DB smoke test

Run the full non-database lifecycle with automatic report output:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_no_db.ps1 -ReportPath smoke_no_db_report.json
```

The report includes parse/extract metadata and snapshot delta counts in
`smoke_no_db_report.json`.

## Release check

Run both the full quality gate and no-DB smoke in one command:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```
