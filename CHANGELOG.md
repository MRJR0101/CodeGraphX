# Changelog

## Unreleased

## 0.3.0 - 2026-04-10

### Docs and Tests (Batch D)
- README version badge bumped to 0.3.0.
- README Quick Start now documents `codegraphx pipeline run --skip-load`.
- README command tables updated with `pipeline run`, `analyze churn-hotspots`,
  and the real `completions <shell>` behavior.
- New README section "Shell Completion (0.3.0+)" with a copy-paste PowerShell
  profile snippet.
- Unit test coverage added for `parsers/javascript` (6 tests covering
  regex fallback, tree-sitter branch, TypeScript, empty input, and control
  flow keyword filtering).
- Unit test coverage added for `cli/commands/enrich` (8 tests covering all
  seven subcommands plus the missing-script error path).

### New Features (Batch C)
- `codegraphx pipeline run` -- one-shot orchestration command that runs
  scan -> parse -> extract -> (optional) load and writes a machine-readable
  manifest to `<out_dir>/pipeline_run_manifest.json`. Supports `--skip-load`
  (default), `--with-load`, `--relations/--no-relations`, `--force-full`,
  `--fresh`, `--no-snapshot`, and `--snapshot-label`. Each stage entry records
  status, duration, output path, record count, and any error.
- `codegraphx completions <shell>` now emits real completion scripts for
  PowerShell (first-class), bash, zsh, and fish. PowerShell output can be
  piped into `$PROFILE` directly via `Out-File -Encoding utf8`.
- `codegraphx analyze churn-hotspots` -- churn-aware hotspot ranking that
  reads `events.jsonl` for per-file function/edge counts, runs
  `git log --numstat` per project root, and combines coupling with churn
  using a log-weighted score. Runs without Neo4j. Supports `--since`,
  `--project`, `--top`, and `--output`.
- `core/churn.py` -- new pure helper module providing `parse_numstat`,
  `compute_churn`, `rank_hotspots`, `file_stats_from_events`, and
  `churn_weight`. Git invocation is injectable for deterministic testing.

### Bug Fixes
- `analyze hotspots` and `analyze metrics` now use `[:CALLS_FUNCTION]` edges for
  fan-in/fan-out calculation. Previously used `[:CALLS]` (Symbol edges), causing
  fan-in to always read zero.
- AST Python parser nested function scope handling now matches tree-sitter behavior.
  Calls inside inner functions are attributed to the inner function, not the enclosing one.
- `_looks_write_query` guard now uses regex clause-boundary anchors instead of substring
  match, preventing false positives on identifiers like `creator` or `updater`.
- `_resolve_query` file reads restricted to `.cypher` extension only.
- `_sha1` renamed to `_content_hash`; implementation uses SHA-256 (was already SHA-256,
  name was misleading).
- Duplicate `_event_identity` function removed from `neo4j_client.py`; canonical
  definition in `snapshots.py` is now imported.
- `GraphDatabase` and hash imports moved to module level in `neo4j_client.py`
  (were deferred inside hot functions).
- Ghost-node warning comment added to `_merge_edge` in `neo4j_client.py`.
- `run_extract` redundant first pass removed; function definitions and pending call
  edges are now collected in the same loop as event generation.
- `pytest` moved to dev dependencies in `requirements.txt`.
- `.env.example` updated to document all required environment variables including
  `MEMGRAPH_URI` and `MEILISEARCH_INDEX`.

### New Features
- Parser modules extracted from `stages.py` into a dedicated `core/parsers/` package:
  - `parsers/python.py` -- Python AST and tree-sitter parsing
  - `parsers/javascript.py` -- JS/TS tree-sitter and regex fallback parsing
  - `parsers/__init__.py` -- re-exports `parse_python` and `parse_js`
  - `stages.py` is now thin orchestration only (~200 lines, was 700)
- SQLite FTS5 search index (`search.db`) built by `load` command after every successful load:
  - `core/search_index.py` provides `build_search_index` and `query_search_index`
  - `search` command uses FTS index when available, falls back to O(n) JSONL scan otherwise
  - `doctor` checks for `search.db` and warns if a scan exists but the index has not been built
  - `search.db` path added to `Paths` dataclass in `stages.py`
- `start-neo4j.ps1` -- Docker-based Neo4j startup helper script. Reads credentials
  from `.env`, creates or restarts the `neo4j-cgx` container, and polls until ready.
  Safe to commit publicly (no hardcoded credentials).

## 0.2.0

- Added the canonical `src/codegraphx` package layout and Typer-based CLI entrypoint.
- Shipped deterministic scan, parse, extract, load, snapshot, delta, and analysis workflows.
- Added optional Neo4j integration plus no-database JSONL-first operation.
- Added CI, linting, typing, and test automation for the packaged CLI.

## 0.1.0

- Initial project scaffolding.
