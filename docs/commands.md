# Command Reference

## Top-Level Commands

- `scan`
- `parse`
- `extract`
- `load`
- `query`
- `search`
- `ask`
- `compare`
- `impact`
- `delta`
- `doctor`
- `snapshots` (group)
- `analyze` (group)
- `completions`

## Core Pipeline

### `scan`

Discover files from configured projects.

```bash
codegraphx scan --config config/projects.yaml --settings config/default.yaml
```

### `parse`

Parse scanned files into AST-like summaries with cache support.

```bash
codegraphx parse --settings config/default.yaml
```

### `extract`

Generate graph events from parse output.

```bash
codegraphx extract --settings config/default.yaml --relations
```

### `load`

Incrementally load events into Neo4j.

```bash
codegraphx load --settings config/default.yaml
```

## Snapshot and Delta

### `snapshots list`

```bash
codegraphx snapshots list
```

### `snapshots create`

Uses `load.state.json` hashes when available, otherwise hashes `events.jsonl`.

```bash
codegraphx snapshots create --label baseline
```

### `snapshots diff`

```bash
codegraphx snapshots diff <old> <new> --show-keys
```

### `snapshots report`

```bash
codegraphx snapshots report <old> <new> --output report.json
```

### `delta`

```bash
codegraphx delta <old> <new> --show-lists --output delta.json
```

## Analysis and Impact

### `impact`

Find direct and transitive callers of a symbol.

```bash
codegraphx impact authenticate_user --project my_project --depth 4 --limit 100
```

### `analyze`

Available subcommands: `metrics`, `hotspots`, `security`, `debt`, `refactor`, `duplicates`, `patterns`, `full`.

```bash
codegraphx analyze metrics --project my_project
```

## Querying

### `query`

Execute Cypher string or `.cypher` file.

```bash
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10" --safe
```

### `search`

Search over extracted events.

```bash
codegraphx search auth --index functions --limit 20
```

### `ask`

Template-based NL-to-query helper.

```bash
codegraphx ask "show duplicate functions" --project my_project
```

## Diagnostics

### `doctor`

Run environment and service checks.

```bash
codegraphx doctor --skip-neo4j
```

## Completion

```bash
codegraphx completions powershell
```
