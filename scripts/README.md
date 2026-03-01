# Scripts

Operational scripts for local setup, validation, and large-repository scanning.

## Included Scripts

- `smoke_no_db.ps1`
  - Runs a no-database smoke pipeline (scan/parse/extract/snapshots/delta) against fixture repos.
- `release_check.ps1`
  - Basic release gate checks before tagging/publishing.
- `bootstrap_neo4j_docker.ps1`
  - Starts a local Neo4j Docker instance and applies schema bootstrap script.
- `bootstrap_neo4j.cypher`
  - Cypher schema bootstrap queries for Neo4j.
- `install_grammars.py`
  - Placeholder utility for grammar setup/validation.
- `pre-commit.py`
  - Local pre-commit style analysis helper.
- `chunked_scan_enrich.py`
  - Runs chunked `codegraphx scan` for very large roots, merges results, and can upsert scan summary into SQLite enrichment DB.
- `enrichment_backlog.py`
  - Ranks project rows from unified catalog DB by enrichment value to choose next scan/enrichment targets.
- `enrichment_campaign.py`
  - Plans or executes multi-project enrichment campaigns by selecting top backlog candidates and running chunked scans per candidate.
- `sqlite_index_audit.py`
  - Audits SQLite indexes for `projects` and `codegraphx_enrichment`, with optional auto-creation of missing recommended indexes.
- `file_collector_signals.py`
  - Detects likely scripts that collect/analyze other files and persists per-file + project summary signals into SQLite.
- `code_intelligence_signals.py`
  - Computes dependency edges, call edges, complexity, and similarity pairs from scan artifacts and persists them to SQLite.

## Requirements

- Python 3.10+
- PowerShell 7+
- `uv` installed and available in `PATH`
- CodeGraphX dependencies installed (`uv sync`)

## Quick Commands

```powershell
cd C:\Repository\codegraphx\scripts

# No-DB smoke test
powershell -ExecutionPolicy Bypass -File .\smoke_no_db.ps1 -ReportPath ..\smoke_no_db_report.json

# Release check
powershell -ExecutionPolicy Bypass -File .\release_check.ps1

# Neo4j bootstrap
powershell -ExecutionPolicy Bypass -File .\bootstrap_neo4j_docker.ps1
```

## Large Root Scan (Chunked)

Use this when a single scan is too large/noisy (for example, `00_PyToolbelt`).

```powershell
cd C:\Repository\codegraphx
uv run python .\scripts\chunked_scan_enrich.py `
  --target-root "<source-root>" `
  --chunk-size 6 `
  --tag pytoolbelt `
  --update-db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --source-project pytoolbelt

# Resume an interrupted run
uv run python .\scripts\chunked_scan_enrich.py `
  --target-root "<source-root>" `
  --chunk-size 6 `
  --tag pytoolbelt `
  --resume `
  --update-db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --source-project pytoolbelt

# Planning mode (generate chunk configs only)
uv run python .\scripts\chunked_scan_enrich.py `
  --target-root "<source-root>" `
  --chunk-size 6 `
  --tag pytoolbelt `
  --dry-run
```

Outputs:

- Chunk configs:
  - `config/<tag>_chunks/projects_chunk_XX.yaml`
  - `config/<tag>_chunks/settings_chunk_XX.yaml`
- Chunk artifacts:
  - `data/<tag>_chunks/chunk_XX/scan.jsonl`
- Final merged artifacts:
  - `data/<tag>_scan_complete/scan_merged_<tag>.jsonl`
  - `data/<tag>_scan_complete/scan_summary_<tag>.json`

If `--update-db` is provided, the script upserts `codegraphx_enrichment` for `source_path=<target-root>` with merged scan counts and artifact pointers.

## Enrichment Backlog Ranking

```powershell
cd C:\Repository\codegraphx

# Top 20 non-enriched candidates
uv run python .\scripts\enrichment_backlog.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --limit 20

# Only candidates under c:\Dev\PROJECTS in JSON
uv run python .\scripts\enrichment_backlog.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --root-prefix "c:\Dev\PROJECTS" `
  --limit 50 `
  --json `
  --output "C:\Repository\codegraphx\data\enrichment_backlog_dev_projects.json"
```

## Campaign Automation (Multiple Projects)

Use this to continuously grow enrichment coverage from ranked DB candidates.

```powershell
cd C:\Repository\codegraphx

# Plan next 5 targets without running scans
uv run python .\scripts\enrichment_campaign.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --limit 5 `
  --min-lines 1000 `
  --root-prefix "c:\Dev\PROJECTS"

# Execute campaign scans (resumable)
uv run python .\scripts\enrichment_campaign.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --limit 3 `
  --min-lines 1500 `
  --root-prefix "c:\Dev\PROJECTS" `
  --tag-prefix growth `
  --chunk-size 6 `
  --resume `
  --execute `
  --stop-on-error
```

Campaign manifests are written to `data/enrichment_campaigns/campaign_<timestamp>.json` unless `--output` is provided.

CLI wrappers are also available:

```powershell
uv run codegraphx enrich backlog --db "C:\Repository\ProjectCatalog\project_catalog.db" --limit 20
uv run codegraphx enrich campaign --db "C:\Repository\ProjectCatalog\project_catalog.db" --limit 3 --execute --resume
uv run codegraphx enrich index-audit --db "C:\Repository\ProjectCatalog\project_catalog.db"
uv run codegraphx enrich collectors --db "C:\Repository\ProjectCatalog\project_catalog.db" --source-path "<source-root>"
uv run codegraphx enrich intelligence --db "C:\Repository\ProjectCatalog\project_catalog.db" --source-path "<source-root>"
```

## File Collector Signals

Persist reusable detection signals so you can query which files act like scanners/indexers/auditors.

```powershell
cd C:\Repository\codegraphx

# Use latest enrichment scan artifact for project root
uv run python .\scripts\file_collector_signals.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --source-path "<source-root>" `
  --exclude-subpath "AssessmentInbox\\devwide\\incoming,AssessmentInbox\\devwide_rescan" `
  --min-score 4.0 `
  --top 100 `
  --json `
  --output "C:\Repository\codegraphx\data\pytoolbelt_collectors.json"

# Analyze only (no DB write)
uv run python .\scripts\file_collector_signals.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --source-path "<source-root>" `
  --dry-run
```

Notes:
- Default behavior replaces prior `codegraphx_file_signals` rows for the same `source_path` so reruns stay consistent.
- Use `--append` to retain prior rows and only upsert current results.

SQLite tables created/updated:
- `codegraphx_file_signals` (per-file classifier features and score)
- `codegraphx_project_signals` (project-level summary)

## Code Intelligence Signals

Use this for reusable graph-style intelligence without writing many artifact files.

```powershell
cd C:\Repository\codegraphx

uv run python .\scripts\code_intelligence_signals.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --source-path "<source-root>" `
  --exclude-subpath "assessmentinbox" `
  --min-file-sim 0.65 `
  --min-func-sim 0.8 `
  --max-file-pairs 1000 `
  --max-func-pairs 2000
```

Notes:
- Built-in default excludes automatically skip common low-signal trees (`.venv`, `node_modules`, build caches, browser mirrors under `ms-playwright`).
- Add `--no-default-excludes` when you intentionally want full coverage including vendored/generated content.

SQLite tables created/updated:
- `codegraphx_project_intelligence`
- `codegraphx_dependency_edges`
- `codegraphx_call_edges`
- `codegraphx_complexity_nodes`
- `codegraphx_similarity_pairs`

## SQLite Index Audit

Use this before large backlog/campaign queries to keep SQLite lookups fast.

```powershell
cd C:\Repository\codegraphx

# Audit only
uv run python .\scripts\sqlite_index_audit.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db"

# Audit and apply missing recommended indexes
uv run python .\scripts\sqlite_index_audit.py `
  --db "C:\Repository\ProjectCatalog\project_catalog.db" `
  --apply `
  --json `
  --output "C:\Repository\codegraphx\data\sqlite_index_audit_report.json"
```

## Safety Notes

- Script operations are additive: generated files are written under `config/*_chunks` and `data/*_chunks`/`data/*_scan_complete`.
- Campaign planning/execution writes manifests under `data/enrichment_campaigns`.
- No project source files are modified.
- SQLite updates are performed with `INSERT ... ON CONFLICT ... DO UPDATE`.
- Index updates use `CREATE INDEX IF NOT EXISTS` and do not drop/alter existing indexes.

---
Part of PyToolbelt ecosystem.
