# Schema

## Node Labels

| Label | Key Properties |
|-------|----------------|
| `Project` | `name` |
| `File` | `uid`, `project`, `path`, `rel_path`, `language`, `line_count` |
| `Function` | `uid`, `name`, `line`, `project`, `file_uid`, `signature_hash` |
| `Symbol` | `uid`, `name` |
| `Module` | `uid`, `name` |

## Edge Types

| Edge | Direction | Meaning |
|------|-----------|---------|
| `CONTAINS` | `Project -> File` | A project owns a file |
| `DEFINES` | `File -> Function` | A file defines a function |
| `CALLS` | `Function/File -> Symbol` | A call to an unresolved or external symbol |
| `CALLS_FUNCTION` | `Function -> Function` | A resolved intra-project function call |
| `IMPORTS` | `File -> Module` | A file imports a module |

## Event Identity

Used for incremental load deduplication and snapshot comparison.

### Node identity key

`node:<label>:<uid>`

### Edge identity key

`edge:<type>:<src_label>:<src_uid>:<dst_label>:<dst_uid>`

## UID Patterns

### Project

`<project_name>`

### File

`<project>:<rel_path>`

### Function

`<project>:<rel_path>:<function_name>:<line>`

### Symbol

`symbol:<name>`

### Module

`module:<name>`

## Hashing

- Content hash: SHA-256 of UTF-8 encoded text (used for parse-row and file caching).
- Event hash: SHA-256 of stable JSON payload (used for incremental load state).
- Signature hash: SHA-256 of `<project>|<rel_path>|<function_name>` (used for duplicate detection).

## Pipeline Artifacts

| File | Stage | Purpose |
|------|-------|---------|
| `scan.jsonl` | scan | File inventory |
| `ast.jsonl` | parse | Parsed functions, imports, calls |
| `parse.cache.json` | parse | Per-file content hash cache |
| `parse.meta.json` | parse | Parse run statistics |
| `events.jsonl` | extract | Graph node and edge events |
| `extract.cache.json` | extract | Per-row event cache |
| `extract.meta.json` | extract | Extract run statistics |
| `load.state.json` | load | Loaded event hashes for incremental state |
| `load.meta.json` | load | Load run statistics |
| `search.db` | load | SQLite FTS5 index of node names and paths |
| `snapshots/*.json` | snapshots | Point-in-time hash snapshots |
