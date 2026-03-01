# CodeGraphX

[![CI](https://github.com/MRJR0101/CodeGraphX/actions/workflows/ci.yml/badge.svg)](https://github.com/MRJR0101/CodeGraphX/actions/workflows/ci.yml)
[![Python 3.10-3.13](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-orange)](CHANGELOG.md)

A deterministic code intelligence pipeline that scans source repositories, parses
code into structured facts using tree-sitter, builds a knowledge graph of
projects/files/functions/calls, and enables fast impact analysis, snapshot diffs,
and trend reporting.

---

## Why CodeGraphX

Most code analysis tools either require a running IDE or depend on cloud services.
CodeGraphX is different:

- **Local-first** -- runs entirely on your machine, no network required
- **Deterministic** -- same input always produces same output via content hashing
- **Incremental** -- only re-processes files that changed
- **DB-optional** -- the full pipeline works without Neo4j using JSONL artifacts
- **CI-ready** -- tested on Ubuntu + Windows across Python 3.10-3.13

The pipeline produces stable JSONL artifacts at every stage, so you can inspect,
replay, and audit every step before touching a database.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/MRJR0101/CodeGraphX.git
cd CodeGraphX
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -e ".[dev]"

# Or with uv (recommended)
uv sync --all-extras
```

### Verify Installation

```bash
codegraphx --version
codegraphx --help
```

If you cloned the repo and directly run `python cli/main.py`, the legacy shim now
points to the canonical CLI but still requires dependencies to be installed first.
Use:

```bash
pip install -e .
python -m codegraphx --help
```

### Run the Pipeline (No Database Required)

```bash
# 1. Configure your project roots
cp config/projects.example.yaml config/projects.yaml
# Edit config/projects.yaml to point at your code

# 2. Run the pipeline
codegraphx scan                # Discover files -> data/scan.jsonl
codegraphx parse               # Parse with tree-sitter -> data/ast.jsonl
codegraphx extract             # Extract facts -> data/events.jsonl

# 3. Inspect results
cat data/events.jsonl | python -m json.tool | head -50
```

### Run with Neo4j (Optional)

```bash
# Set up Neo4j credentials
cp .env.example .env
# Edit .env with your Neo4j connection details

# Load the graph
codegraphx load

# Query it
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10"
```

---

## Architecture

```
Source Code
    |
    v
[scan] --> scan.jsonl           Enumerate files by extension + exclude rules
    |
    v
[parse] --> ast.jsonl           Tree-sitter parsing with fallback strategies
    |                           Cached: parse.cache.json, parse.meta.json
    v
[extract] --> events.jsonl      Semantic facts: Functions, Classes, CALLS, IMPORTS
    |                           Cached: extract.cache.json, extract.meta.json
    v
[load] --> Neo4j graph          Incremental apply with state tracking
    |                           State: load.state.json, load.meta.json
    v
[analyze/query/impact/delta]    Analysis, querying, impact tracing, diffs
```

Every stage writes deterministic JSONL so you can replay or inspect without
re-running earlier stages.

### Graph Schema

| Node | Properties |
|------|-----------|
| Project | name |
| File | path, project |
| Function | name, path, start_line, end_line, params, project |
| Symbol | name, path, project |

| Edge | Meaning |
|------|---------|
| CONTAINS | Project -> File |
| DEFINES | File -> Function |
| CALLS | Function/File -> Symbol |
| CALLS_FUNCTION | Function -> Function |

---

## Commands

### Core Pipeline

| Command | What It Does |
|---------|-------------|
| `scan` | Discover files from configured project roots |
| `parse` | Parse files into AST summaries with tree-sitter |
| `extract` | Extract semantic graph events (nodes + edges) |
| `load` | Incrementally load events into Neo4j |

### Analysis

| Command | What It Does |
|---------|-------------|
| `analyze metrics` | Code metrics per project |
| `analyze hotspots` | High-complexity / high-change areas |
| `analyze security` | Security-relevant patterns |
| `analyze debt` | Technical debt indicators |
| `analyze duplicates` | Duplicate function detection |
| `analyze patterns` | Code pattern recognition |
| `analyze full` | Run all analysis modules |

### Snapshot and Change Tracking

| Command | What It Does |
|---------|-------------|
| `snapshots create` | Create a named snapshot from current state |
| `snapshots list` | List all snapshots |
| `snapshots diff` | Compare two snapshots |
| `snapshots report` | Generate a change report between snapshots |
| `delta` | Detailed change summary between snapshots |

### Querying and Search

| Command | What It Does |
|---------|-------------|
| `query` | Execute Cypher queries against the graph |
| `search` | Search functions/symbols |
| `ask` | Template-based natural language queries |
| `compare` | Compare two projects (shared functions, call trees) |
| `impact` | Find direct and transitive callers of a symbol |

### Utilities

| Command | What It Does |
|---------|-------------|
| `doctor` | Environment and service health checks |
| `completions` | Shell completion hints |

---

## Example: Impact Analysis

Find every function that directly or transitively calls `authenticate_user`:

```bash
codegraphx impact authenticate_user --project my_project --depth 4 --limit 100
```

This traverses the call graph up to 4 levels deep and reports every caller,
showing you exactly what breaks if you change that function.

---

## Example: Snapshot Diffs

Track how your codebase changes over time:

```bash
# Create a baseline snapshot
codegraphx snapshots create --label before-refactor

# ... make changes to your code ...

# Re-run the pipeline
codegraphx scan && codegraphx parse && codegraphx extract

# Create a new snapshot and diff
codegraphx snapshots create --label after-refactor
codegraphx delta before-refactor after-refactor --show-lists
```

---

## Configuration

### Project Configuration (config/projects.yaml)

```yaml
projects:
  - name: MyApp
    root: C:/Dev/MyApp
    exclude:
      - .venv
      - __pycache__
      - node_modules
```

### Runtime Settings (config/default.yaml)

```yaml
run:
  out_dir: data
  max_files: 0              # 0 = no limit
  include_ext: [".py", ".js", ".ts"]

neo4j:
  uri: ${NEO4J_URI:-bolt://localhost:7687}
  user: ${NEO4J_USER:-neo4j}
  password: ${NEO4J_PASSWORD:-codegraphx123}
  database: neo4j
```

Environment variables are supported with `${VAR:-default}` syntax.

### Supported Languages

- Python (.py)
- JavaScript (.js)
- TypeScript (.ts)

Parsing uses tree-sitter with automatic fallback strategies.

---

## Testing

```bash
# Run all tests
pytest -q

# Run with uv
uv run pytest -q

# Run the no-DB smoke test (Windows)
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_no_db.ps1 -ReportPath smoke_report.json

# Full release check
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

CI runs on every push: lint (ruff), type check (mypy), tests (pytest), and
package build across Ubuntu + Windows on Python 3.10-3.13.

---

## Security

- Cypher queries are parameterized in all command paths that accept user input
- `query --safe` provides a lexical guard for ad-hoc query execution
- Path validation prevents directory traversal in parse/extract stages
- Credentials belong in environment variables, not config files

See [docs/security-architecture.md](docs/security-architecture.md) for the full
threat model and operational guidance.

---

## Documentation

| Document | What It Covers |
|----------|---------------|
| [docs/design.md](docs/design.md) | Architecture and execution model |
| [docs/commands.md](docs/commands.md) | Full command reference |
| [docs/schema.md](docs/schema.md) | Graph schema and identity model |
| [docs/queries.md](docs/queries.md) | Common Cypher query patterns |
| [docs/roadmap.md](docs/roadmap.md) | Planned features and milestones |
| [docs/security-architecture.md](docs/security-architecture.md) | Security controls and guidance |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [FEATURE_REPORT.md](FEATURE_REPORT.md) | Comprehensive feature documentation |

---

## Compatibility

| Component | Supported |
|-----------|-----------|
| Python | 3.10, 3.11, 3.12, 3.13 |
| OS | Windows, Linux (CI-tested) |
| Neo4j | 5.x (optional) |

---

## License

[MIT](LICENSE)
