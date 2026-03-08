# Command Reference

## Top-Level Commands

| Command | Group | Purpose |
|---------|-------|---------|
| `scan` | pipeline | Discover source files |
| `parse` | pipeline | Parse files into AST records |
| `extract` | pipeline | Generate graph events |
| `load` | pipeline | Load events into Neo4j + build search index |
| `query` | query | Run Cypher against Neo4j |
| `search` | query | Full-text search over extracted nodes |
| `ask` | query | Template-based NL-style queries |
| `compare` | query | Compare two projects |
| `impact` | query | Trace callers of a symbol |
| `delta` | diff | Detailed snapshot delta report |
| `snapshots` | diff | Snapshot lifecycle (create/list/diff/report) |
| `analyze` | analysis | Metrics, hotspots, security, refactor patterns |
| `enrich` | enrichment | Repo catalog enrichment workflows |
| `doctor` | diagnostics | Validate environment and connectivity |
| `completions` | diagnostics | Shell completion guidance |

---

## Core Pipeline

### `scan`

Discover files from configured projects.

```bash
codegraphx scan
codegraphx scan --config config/projects.yaml --settings config/default.yaml
```

### `parse`

Parse scanned files into AST-like summaries. Uses tree-sitter when available,
falls back to stdlib `ast` (Python) or regex (JS/TS). Results are cached by
content hash so unchanged files are skipped on re-runs.

```bash
codegraphx parse
codegraphx parse --settings config/default.yaml
```

### `extract`

Generate graph events from parse output. Resolves intra-project
`CALLS_FUNCTION` edges after the full function map is built.

```bash
codegraphx extract
codegraphx extract --no-relations   # skip edge events
```

### `load`

Incrementally load events into Neo4j. Skips events already in the graph.
After a successful load, rebuilds the SQLite FTS search index (`data/search.db`).

```bash
codegraphx load
codegraphx load --force-full         # ignore incremental state, reload everything
codegraphx load --no-snapshot        # skip snapshot creation
codegraphx load --snapshot-label v1  # tag the created snapshot
```

---

## Search and Query

### `search`

Search extracted nodes by name or path. Uses the SQLite FTS5 index
(`data/search.db`) when available (built by `load`). Falls back to an O(n)
JSONL scan before the first `load`.

```bash
codegraphx search authenticate
codegraphx search parse --index functions       # functions only
codegraphx search handler --index symbols       # symbols and modules only
codegraphx search run --project dreamextractor  # filter to one project
codegraphx search auth --limit 50
```

### `query`

Execute a Cypher string or `.cypher` file against Neo4j.

```bash
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10"
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10" --safe
codegraphx query path/to/query.cypher
```

`--safe` enables a lexical write-guard. Queries matching write clause patterns
(`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`) are rejected.

### `ask`

Template-based NL-style query helper. Currently a stub -- outputs the
interpreted query plan without executing against a live LLM.

```bash
codegraphx ask "show duplicate functions" --project my_project
```

### `compare`

Compare two projects side by side.

```bash
codegraphx compare project_a project_b
```

### `impact`

Trace direct and transitive callers of a function via `CALLS_FUNCTION` edges.

```bash
codegraphx impact authenticate_user
codegraphx impact run --project dreamextractor --depth 4 --limit 100
```

---

## Snapshots and Delta

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
codegraphx snapshots diff <old_snapshot> <new_snapshot>
codegraphx snapshots diff <old> <new> --show-keys
```

### `snapshots report`

```bash
codegraphx snapshots report <old> <new> --output report.json
```

### `delta`

Detailed snapshot delta with categorised changes.

```bash
codegraphx delta <old> <new>
codegraphx delta <old> <new> --show-lists --output delta.json
```

---

## Analysis

All `analyze` subcommands accept `--project` to filter to a single project.

### `analyze metrics`

Function fan-in and fan-out via resolved `CALLS_FUNCTION` edges.

```bash
codegraphx analyze metrics
codegraphx analyze metrics --project codegraphx --limit 30
```

### `analyze hotspots`

Top 25 functions by total coupling (fan-in + fan-out).

```bash
codegraphx analyze hotspots
codegraphx analyze hotspots --project dreamextractor
```

### `analyze security`

Name-pattern based security signal queries (auth, crypt, exec, etc.).

```bash
codegraphx analyze security
codegraphx analyze security --category auth
```

### `analyze debt`

Aggregate debt-style summary across the loaded graph.

```bash
codegraphx analyze debt
```

### `analyze refactor`

Name-filtered refactor candidates.

```bash
codegraphx analyze refactor
```

### `analyze duplicates`

Functions sharing the same `signature_hash`.

```bash
codegraphx analyze duplicates
```

### `analyze patterns`

Pattern-oriented function search.

```bash
codegraphx analyze patterns
```

### `analyze full`

Multi-section summary report covering metrics, hotspots, security signals, and debt.

```bash
codegraphx analyze full
codegraphx analyze full --project codegraphx
```

---

## Enrichment

Enrichment commands support batch repo analysis workflows using a local SQLite catalog.

### `enrich backlog`

Rank candidate repos from a SQLite project catalog.

```bash
codegraphx enrich backlog --db catalog.db --limit 20
```

### `enrich chunk-scan`

Run chunked scans against a target root directory.

```bash
codegraphx enrich chunk-scan --root C:/path/to/repos --chunk-size 10
```

### `enrich campaign`

Plan or execute a ranked enrichment campaign.

```bash
codegraphx enrich campaign --plan --db catalog.db
codegraphx enrich campaign --run --db catalog.db
```

### `enrich index-audit`

Audit recommended SQLite indexes for a catalog database.

```bash
codegraphx enrich index-audit --db catalog.db
```

### `enrich collectors`

Compute collector-style project signals (file counts, language breakdown, etc.).

```bash
codegraphx enrich collectors --db catalog.db
```

### `enrich intelligence`

Compute similarity and intelligence signals across catalogued repos.

```bash
codegraphx enrich intelligence --db catalog.db
```

---

## Diagnostics

### `doctor`

Validate config files, required Python modules, optional Neo4j connectivity,
and the FTS search index.

```bash
codegraphx doctor
codegraphx doctor --skip-neo4j   # skip Neo4j connectivity check
```

Checks reported:

| Check | Passes when |
|-------|-------------|
| `projects_config_exists` | `config/projects.yaml` found |
| `settings_exists` | `config/default.yaml` found |
| `projects_loaded` | Projects config parsed without error |
| `settings_loaded` | Settings file parsed without error |
| `search_db` | `data/search.db` exists (warns if scan exists but index is missing) |
| `module_*` | Required Python packages importable |
| `neo4j_connection` | Bolt connection to Neo4j succeeds |

### `completions`

Print shell-completion guidance.

```bash
codegraphx completions powershell
codegraphx completions bash
```
