# CodeGraphX

[![CI](https://github.com/MRJR0101/CodeGraphX/actions/workflows/ci.yml/badge.svg)](https://github.com/MRJR0101/CodeGraphX/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.3.0-orange)](CHANGELOG.md)

CodeGraphX is a local-first code intelligence CLI that scans repositories, parses
source files into structured facts, emits deterministic graph events, and
supports impact analysis, snapshots, diffs, and optional Neo4j loading.

## Why CodeGraphX

- Deterministic output: unchanged inputs produce stable JSONL artifacts and hashes.
- Incremental execution: parsing, extraction, and graph loading reuse cached state.
- Database optional: `scan`, `parse`, `extract`, `snapshots`, and `delta` work without Neo4j.
- Inspectable pipeline: every stage writes artifacts you can diff, audit, and replay.
- CI covered: the repo is tested on Ubuntu and Windows across Python 3.11 to 3.13.

## Installation

```bash
git clone https://github.com/MRJR0101/CodeGraphX.git
cd CodeGraphX

# pip
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate   # Linux/macOS
pip install -e ".[dev]"

# or uv
uv sync --all-groups
```

Verify the CLI:

```bash
python -m codegraphx --version
python -m codegraphx --help
```

`python cli/main.py` is still supported as a legacy compatibility shim, but the
canonical entrypoints are `python -m codegraphx` and `codegraphx`.

## Quick Start

1. Create a local projects file from the example:

```bash
cp config/projects.example.yaml config/projects.yaml
```

2. Edit `config/projects.yaml` to point at one or more repositories.

3. Run the pipeline. Either drive each stage individually:

```bash
codegraphx scan
codegraphx parse
codegraphx extract
```

...or use the one-shot orchestrator introduced in 0.3.0:

```bash
codegraphx pipeline run --skip-load
```

`pipeline run` chains scan -> parse -> extract (-> optional load) and writes
a machine-readable manifest to `<out_dir>/pipeline_run_manifest.json`. Pass
`--with-load` to include the Neo4j load stage; pass `--manifest PATH` to
override the manifest location.

4. Inspect the first few emitted events:

```bash
Get-Content data/events.jsonl -TotalCount 5   # Windows PowerShell
# head -n 5 data/events.jsonl                 # POSIX shells
```

### Optional Neo4j Setup

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

**Option A -- Docker (recommended for local use):**

```powershell
# Start a Neo4j 5 container using credentials from .env
.\start-neo4j.ps1
```

The script creates a container named `neo4j-cgx`, waits until bolt is ready,
and prints the connection details. Run it any time you need Neo4j. To stop:

```powershell
docker stop neo4j-cgx
```

**Option B -- existing Neo4j instance:**

Point `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in your `.env` at the
running instance.

Then validate and load:

```bash
codegraphx doctor
codegraphx load
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10"
```

After `load`, the `search` command uses a fast SQLite FTS index:

```bash
codegraphx search parse --index functions
```

CodeGraphX loads `.env` automatically when referenced by `config/default.yaml`.

## Pipeline

```text
Source repo(s)
    |
    v
[scan]    -> scan.jsonl            File inventory by project/root/path
    |
    v
[parse]   -> ast.jsonl             Parsed functions/imports/calls
             parse.cache.json
             parse.meta.json
    |
    v
[extract] -> events.jsonl          Project/File/Function/Symbol/Module events
             extract.cache.json
             extract.meta.json
    |
    v
[load]    -> Neo4j                 Incremental merge and stale-record cleanup
             load.state.json
             load.meta.json
    |
    v
[search/query/impact/analyze/delta/snapshots]
```

## Graph Model

| Node | Key Properties |
|------|----------------|
| `Project` | `name` |
| `File` | `uid`, `project`, `path`, `rel_path`, `language`, `line_count` |
| `Function` | `uid`, `name`, `line`, `project`, `file_uid`, `signature_hash` |
| `Symbol` | `uid`, `name` |
| `Module` | `uid`, `name` |

| Edge | Meaning |
|------|---------|
| `CONTAINS` | `Project -> File` |
| `DEFINES` | `File -> Function` |
| `CALLS` | `Function -> Symbol` or `File -> Symbol` |
| `IMPORTS` | `File -> Module` |
| `CALLS_FUNCTION` | `Function -> Function` |

## Commands

### Core Pipeline

| Command | Purpose |
|---------|---------|
| `scan` | Discover project files from `config/projects.yaml` |
| `parse` | Parse supported files into AST-like records |
| `extract` | Convert parsed records into graph events |
| `load` | Incrementally apply events to Neo4j |
| `pipeline run` | One-shot scan -> parse -> extract (-> optional load) with JSON manifest |

### Analysis and Diffs

| Command | Purpose |
|---------|---------|
| `analyze metrics` | Function fan-in/fan-out style metrics |
| `analyze hotspots` | High-line hotspots from loaded graph data |
| `analyze churn-hotspots` | Churn-weighted hotspots combining events.jsonl with `git log --numstat` (no Neo4j) |
| `analyze security` | Name-based security pattern queries |
| `analyze debt` | Aggregate debt-style summaries |
| `analyze refactor` | Name-filtered refactor candidates |
| `analyze duplicates` | Signature-hash duplicate detection |
| `analyze patterns` | Pattern-oriented function search |
| `analyze full` | Multi-section summary report |
| `snapshots create/list/diff/report` | Snapshot lifecycle commands |
| `delta` | Detailed snapshot delta reporting |

### Search and Query

| Command | Purpose |
|---------|---------|
| `query` | Run Cypher against Neo4j |
| `search` | Search extracted events by name/path |
| `ask` | Run template-based NL-style queries |
| `compare` | Compare two projects |
| `impact` | Trace direct and transitive callers |

### Diagnostics and Automation

| Command | Purpose |
|---------|---------|
| `doctor` | Validate config, imports, and optional Neo4j connectivity |
| `completions <shell>` | Emit a completion script for powershell/bash/zsh/fish |
| `enrich backlog` | Rank candidate repos from a SQLite catalog |
| `enrich chunk-scan` | Run chunked scans against a target root |
| `enrich campaign` | Plan or execute ranked enrichment campaigns |
| `enrich index-audit` | Audit recommended SQLite indexes |
| `enrich collectors` | Compute collector-style project signals |
| `enrich intelligence` | Compute similarity and intelligence signals |

## Shell Completion (0.3.0+)

PowerShell (recommended on Windows):

```powershell
codegraphx completions powershell | Out-File -Encoding utf8 $PROFILE.CurrentUserAllHosts
. $PROFILE.CurrentUserAllHosts
```

bash / zsh / fish users can redirect the matching script into their
shell-specific completion file and source it.

## Configuration

Project roots are configured in a local `config/projects.yaml` file:

```yaml
projects:
  - name: DemoPython
    root: C:/path/to/python_project
    exclude:
      - .venv
      - __pycache__
      - dist
      - build
```

Runtime behavior comes from `config/default.yaml`:

```yaml
run:
  out_dir: data
  max_files: 0
  include_ext: [".py", ".js", ".ts"]

neo4j:
  uri: ${NEO4J_URI:-bolt://localhost:7687}
  user: ${NEO4J_USER:-neo4j}
  password: ${NEO4J_PASSWORD:-}
  database: ${NEO4J_DATABASE:-neo4j}
```

Environment variable expansion uses `${VAR:-default}` syntax.

## Validation

```bash
python -m pytest -q
python -m codegraphx --help
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_no_db.ps1 -ReportPath smoke_no_db_report.json
```

For the full local gate, install `uv` and run:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

## Security Notes

- User-supplied Cypher parameters are passed separately from query text.
- `query --safe` adds a lexical guard for ad hoc query execution.
- Path handling in the pipeline avoids traversing outside configured roots.
- Credentials should live in `.env` or environment variables, not committed YAML.

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/README.md](docs/README.md) | Docs entrypoint and navigation |
| [docs/commands.md](docs/commands.md) | Command examples and reference |
| [docs/design.md](docs/design.md) | Architecture and stage behavior |
| [docs/schema.md](docs/schema.md) | Graph entities and identities |
| [docs/queries.md](docs/queries.md) | Query examples and patterns |
| [docs/security-architecture.md](docs/security-architecture.md) | Threat model and safeguards |
| [docs/roadmap.md](docs/roadmap.md) | Planned work |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributor workflow |
| [VERIFY.md](VERIFY.md) | Current validation checklist |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## Compatibility

| Component | Supported |
|-----------|-----------|
| Python | 3.10+ |
| CI matrix | 3.11, 3.12, 3.13 |
| OS | Windows and Linux |
| Neo4j | 5.x |

## License

[MIT](LICENSE)
