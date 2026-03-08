# Design

## Objective

CodeGraphX builds a deterministic code knowledge graph from source files, then
supports analysis, search, and change comparison.

## Stages

### 1. `scan`

Enumerates source files by extension and exclude rules from `config/projects.yaml`.
Output: `scan.jsonl` (one row per file with project, path, rel_path, ext, size).

### 2. `parse`

Parses Python and JS/TS files. Uses tree-sitter when available, falls back to
stdlib `ast` for Python and regex for JS/TS.

Parser implementations live in `src/codegraphx/core/parsers/`:
- `python.py` -- `parse_python(file_text)` using tree-sitter or `ast`
- `javascript.py` -- `parse_js(ext, file_text)` using tree-sitter or regex
- `__init__.py` -- re-exports `parse_python` and `parse_js`

`stages.py` imports from the parsers package and delegates all language-specific
logic there. `stages.py` itself contains only orchestration (scan, parse, extract
loops) and shared utilities (`_content_hash`, `_row_hash`, `data_paths`).

Output: `ast.jsonl` (one row per file with functions, imports, calls, function_calls).
Cache: `parse.cache.json`, `parse.meta.json`.

### 3. `extract`

Converts parsed rows into graph events (nodes and edges). Emits `CALLS` edges to
external/unresolved symbols and resolves intra-project `CALLS_FUNCTION` edges in
a second pass after the full function map is built.

Output: `events.jsonl`.
Cache: `extract.cache.json`, `extract.meta.json`.

### 4. `load`

Incrementally applies events to Neo4j. Computes event hashes and skips already-loaded
events. After loading, rebuilds the SQLite FTS search index (`search.db`).

State: `load.state.json`, `load.meta.json`, `search.db`.

### 5. `search`

Queries the SQLite FTS5 index (`search.db`) when available. Falls back to an O(n)
linear scan of `events.jsonl` if the index has not been built yet (i.e., before
the first `load`).

### 6. `snapshots` + `delta`

Snapshot hash timelines for graph state comparison across runs. Works with
`load.state.json` hashes or direct event hashes.

## Determinism

Stable UIDs and SHA-256 content hashes make results reproducible across runs
with unchanged inputs. Caches are keyed on content hash, not timestamps.

## Execution Model

- File I/O first, database optional.
- Stages can be run independently; later stages consume the JSONL output of earlier ones.
- Strong preference for incremental updates over full reloads.
- All JSONL artifacts are human-readable and can be diffed or replayed.

## Parser Strategy

For each language:

1. Attempt tree-sitter parse (fast, accurate, handles edge cases well).
2. Fall back to stdlib `ast` (Python) or regex (JS/TS) on parse errors or if
   tree-sitter is not installed.

Both paths produce the same output shape: functions, imports, calls, function_calls,
line_count. Nested function scopes are handled consistently in both paths -- calls
inside an inner function are attributed to the inner function, not the enclosing one.
