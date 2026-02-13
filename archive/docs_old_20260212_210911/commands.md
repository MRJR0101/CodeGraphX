# CodeGraphX Command Reference

CodeGraphX is a Tree-sitter to graph pipeline that analyzes codebases and provides insights through Neo4j graph queries and Meilisearch-powered search.

## Installation

### Development Installation (from source)

```bash
# Clone the repository
git clone <repository-url>
cd codegraphx

# Create virtual environment
uv venv

# Activate virtual environment (Windows PowerShell)
.venv\Scripts\Activate

# Install in editable mode
uv pip install -e .

# Install with LLM dependencies (for ask command)
uv pip install -e ".[llm]"
```

### Activation

After installation, ensure the virtual environment is activated:

```powershell
# Windows PowerShell
.venv\Scripts\Activate
```

## Quick Start

```bash
# 1. Configure your projects in config/projects.yaml
# 2. Run the full pipeline
codegraphx scan     # Discover files
codegraphx parse     # Parse files into AST
codegraphx extract   # Extract symbols and relations
codegraphx load     # Load into Neo4j
```

---

## Using Without Global Installation

If `codegraphx` is not in your PATH, run directly with Python or uv:

```bash
# Using uv run (recommended - uses scripts from pyproject.toml)
uv run codegraphx scan

# Using Python directly
python -m codegraphx.cli.main scan

# Run any command with uv run
uv run codegraphx analyze full
uv run codegraphx search "authentication"
```

---

## Core Commands

### [`scan`](src/codegraphx/cli/commands/scan.py)

Discover projects and enumerate files.

```bash
codegraphx scan [OPTIONS]
```

**Options:**
- `--config`: Projects config YAML (default: `config/projects.yaml`)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
codegraphx scan --config projects.yaml
```

---

### [`parse`](src/codegraphx/cli/commands/parse.py)

Parse files into lightweight AST summaries.

```bash
codegraphx parse [OPTIONS]
```

**Options:**
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Prerequisite:** Run `codegraphx scan` first.

**Example:**
```bash
codegraphx parse
```

---

### [`extract`](src/codegraphx/cli/commands/extract.py)

Extract semantic facts (nodes/edges) from source files. Supports Python and JavaScript/TypeScript.

```bash
codegraphx extract [OPTIONS]
```

**Options:**
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)
- `--relations/--no-relations`: Extract relation edges (default: True)

**Prerequisite:** Run `codegraphx parse` first.

**Example:**
```bash
# Extract with relations
codegraphx extract --relations

# Extract without relations (faster)
codegraphx extract --no-relations
```

---

### [`load`](src/codegraphx/cli/commands/load.py)

Load extracted graph events into Neo4j.

```bash
codegraphx load [OPTIONS]
```

**Options:**
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Prerequisite:** Run `codegraphx extract` first.

**Example:**
```bash
codegraphx load
```

---

### [`query`](src/codegraphx/cli/commands/query.py)

Run a Cypher query against the graph and print results.

```bash
codegraphx query <CYPHER_QUERY_OR_FILE> [OPTIONS]
```

**Arguments:**
- `cypher`: Cypher query string or path to `.cypher` file

**Options:**
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)
- `--safe`: Reject write operations for safety (default: False)

**Example:**
```bash
# Run inline query
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10"

# Run from file
codegraphx query queries/my_query.cypher

# Safe mode (read-only)
codegraphx query "MATCH (f:Function) RETURN f.name" --safe
```

---

### [`search`](src/codegraphx/cli/commands/search.py)

Search functions and symbols from extracted events.

```bash
codegraphx search <QUERY> [OPTIONS]
```

**Arguments:**
- `query`: Search query string

**Options:**
- `--project`, `-p`: Filter by project name
- `--index`, `-i`: Index to search (default: `all`, options: `all`, `functions`, `symbols`)
- `--limit`, `-l`: Maximum results (default: 20)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Prerequisite:** Run `codegraphx extract` first.

**Example:**
```bash
# Search all indexes
codegraphx search "authentication"

# Search functions only
codegraphx search "validate" --index functions

# Limit results
codegraphx search "handler" --limit 50

# Filter by project
codegraphx search "database" --project my_project
```

---

### [`ask`](src/codegraphx/cli/commands/ask.py)

Ask a natural language question about your codebase. Uses LLM to translate questions into Cypher queries.

```bash
codegraphx ask "<QUESTION>" [OPTIONS]
```

**Arguments:**
- `question`: Natural language question about code

**Options:**
- `--project`, `-p`: Filter by project name
- `--model`, `-m`: LLM provider (default: `openai`, options: `openai`, `anthropic`)
- `--model-name`, `-M`: Model name (default: `gpt-4o`)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Prerequisites:**
- Neo4j running with graph data loaded
- OpenAI or Anthropic API key set (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)

**Example:**
```bash
# Ask a question
codegraphx ask "What are the main entry points in this codebase?"

# Filter by project
codegraphx ask "How does authentication work?" --project my_project

# Use different model
codegraphx ask "Find all error handling functions" --model anthropic --model-name claude-sonnet
```

---

### [`compare`](src/codegraphx/cli/commands/compare.py)

Compare two projects: shared functions, divergent call trees, metrics, and patterns.

```bash
codegraphx compare <PROJECT_A> <PROJECT_B> [OPTIONS]
```

**Arguments:**
- `project_a`: First project name
- `project_b`: Second project name

**Options:**
- `--mode`, `-m`: Comparison mode (default: `shared`, options: `shared`, `unique-a`, `unique-b`, `metrics`, `patterns`, `calltrees`)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Modes:**
- `shared`: Functions with the same name in both projects
- `unique-a`: Functions only in project A
- `unique-b`: Functions only in project B
- `metrics`: Compare function counts, calls, etc.
- `patterns`: Compare design pattern usage
- `calltrees`: Compare call trees for shared functions

**Example:**
```bash
# Compare shared functions
codegraphx compare project_a project_b

# Show unique functions in project_a
codegraphx compare project_a project_b --mode unique-a

# Compare metrics
codegraphx compare project_a project_b --mode metrics

# Compare design patterns
codegraphx compare project_a project_b --mode patterns

# Compare call trees
codegraphx compare project_a project_b --mode calltrees
```

---

### [`impact`](src/codegraphx/cli/commands/impact.py)

Analyze impact of changing a symbol/function, including transitive callers.

```bash
codegraphx impact <SYMBOL> [OPTIONS]
```

**Arguments:**
- `symbol`: Function/symbol name

**Options:**
- `--project`, `-p`: Optional project filter
- `--depth`, `-d`: Transitive traversal depth (default: 3, range: 1..10)
- `--limit`, `-l`: Maximum rows (default: 50)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
codegraphx impact authenticate_user --project my_project --depth 4
```

---

### [`delta`](src/codegraphx/cli/commands/delta.py)

Compare two snapshots and summarize added/removed/changed identities.

```bash
codegraphx delta <OLD> <NEW> [OPTIONS]
```

**Arguments:**
- `old`: Old snapshot id or path
- `new`: New snapshot id or path

**Options:**
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)
- `--output`, `-o`: Optional JSON output path
- `--show-lists`: Show detailed changed files/functions

**Example:**
```bash
codegraphx delta 20260213T024335Z-old 20260213T024338Z-new --show-lists
```

---

### [`snapshots`](src/codegraphx/cli/commands/snapshots.py)

Manage snapshot timeline data for diffing and reporting.

```bash
codegraphx snapshots <SUBCOMMAND> [OPTIONS]
```

**Subcommands:**
- `list`: List snapshot files
- `create`: Create a new snapshot from load state hashes or event hashes
- `diff`: Compare two snapshots
- `report`: Summarize snapshot changes by category

**Examples:**
```bash
codegraphx snapshots list
codegraphx snapshots create --label baseline
codegraphx snapshots diff 20260213T024335Z-old 20260213T024338Z-new --show-keys
codegraphx snapshots report 20260213T024335Z-old 20260213T024338Z-new --output report.json
```

---

## Analysis Commands

The `analyze` command group provides comprehensive code analysis:

### [`codegraphx analyze metrics`](src/codegraphx/cli/commands/analyze.py)

Show code quality metrics (fan-in, fan-out).

```bash
codegraphx analyze metrics [OPTIONS]
```

**Options:**
- `--project`, `-p`: Filter by project name
- `--limit`, `-l`: Result limit (default: 20)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
codegraphx analyze metrics --limit 50
```

---

### [`codegraphx analyze hotspots`](src/codegraphx/cli/commands/analyze.py)

Identify code hotspots (complex, frequently used areas).

```bash
codegraphx analyze hotspots [OPTIONS]
```

**Options:**
- `--project`, `-p`: Filter by project name
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
codegraphx analyze hotspots
```

---

### [`codegraphx analyze security`](src/codegraphx/cli/commands/analyze.py)

Scan for security vulnerabilities.

```bash
codegraphx analyze security [OPTIONS]
```

**Options:**
- `--project`, `-p`: Filter by project name
- `--category`, `-c`: Filter by category (sql_injection, command_injection, hardcoded_secrets, insecure_crypto, path_traversal)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
# Scan all categories
codegraphx analyze security

# Scan specific category
codegraphx analyze security --category sql_injection
```

---

### [`codegraphx analyze debt`](src/codegraphx/cli/commands/analyze.py)

Analyze technical debt and calculate debt score.

```bash
codegraphx analyze debt [OPTIONS]
```

**Options:**
- `--project`, `-p`: Filter by project name
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
codegraphx analyze debt
```

---

### [`codegraphx analyze refactor`](src/codegraphx/cli/commands/analyze.py)

Get refactoring suggestions for code improvements.

```bash
codegraphx analyze refactor [OPTIONS]
```

**Options:**
- `--project`, `-p`: Filter by project name
- `--type`, `-t`: Filter by pattern type (long_function, large_class, feature_envy, data_class, high_coupling)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
# Show all suggestions
codegraphx analyze refactor

# Filter by type
codegraphx analyze refactor --type long_function
```

---

### [`codegraphx analyze duplicates`](src/codegraphx/cli/commands/analyze.py)

Find duplicate or similar functions.

```bash
codegraphx analyze duplicates [OPTIONS]
```

**Options:**
- `--limit`, `-l`: Result limit (default: 20)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
codegraphx analyze duplicates --limit 50
```

---

### [`codegraphx analyze patterns`](src/codegraphx/cli/commands/analyze.py)

Detect design patterns (factories, singletons, observers, repositories, plugins).

```bash
codegraphx analyze patterns [OPTIONS]
```

**Options:**
- `--type`, `-t`: Pattern type (default: `all`, options: factories, singletons, observers, repositories, plugins, all)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
# Detect all patterns
codegraphx analyze patterns

# Detect specific pattern
codegraphx analyze patterns --type factories
```

---

### [`codegraphx analyze full`](src/codegraphx/cli/commands/analyze.py)

Run all analyses and generate a comprehensive report.

```bash
codegraphx analyze full [OPTIONS]
```

**Options:**
- `--project`, `-p`: Filter by project name
- `--output`, `-o`: Save report to file (JSON)
- `--settings`: Runtime settings YAML (default: `config/default.yaml`)

**Example:**
```bash
# Run full analysis
codegraphx analyze full

# Save report to file
codegraphx analyze full --output report.json
```

---

## Shell Completions

Generate shell completions for autocomplete support.

```bash
codegraphx completions <SHELL>
```

**Arguments:**
- `shell`: Shell type (bash, zsh, fish, powershell)

**Example:**
```bash
# Bash
eval "$(codegraphx completions bash)"

# Zsh
eval "$(codegraphx completions zsh)"

# Fish
codegraphx completions fish | source

# PowerShell
codegraphx completions powershell | Out-String | Invoke-Expression
```

---

## Configuration

### Projects Config (`config/projects.yaml`)

Define your projects to analyze:

```yaml
projects:
  - name: my_project
    root: /path/to/project
  - name: another_project
    root: /path/to/another
```

### Settings Config (`config/default.yaml`)

Configure runtime settings:

```yaml
neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "${NEO4J_PASSWORD:-please-change}"
  database: "neo4j"

meilisearch:
  enabled: false
  host: "localhost"
  port: 7700

run:
  out_dir: "data"
  include_ext:
    - ".py"
    - ".js"
    - ".ts"
  max_files: 10000
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for `ask` command |
| `ANTHROPIC_API_KEY` | Anthropic API key for `ask` command |

---

## Common Workflows

### Full Pipeline

```bash
codegraphx scan
codegraphx parse
codegraphx extract
codegraphx load
```

### Quick Analysis

```bash
# After loading data
codegraphx analyze full
```

### Compare Projects

```bash
codegraphx compare project_a project_b
```

### Natural Language Query

```bash
codegraphx ask "What are the most complex functions?"
```

---

## Output Files

The pipeline generates intermediate files in the `data/` directory:

| Stage | File | Description |
|-------|------|-------------|
| scan | `data/scan.jsonl` | Discovered files list |
| parse | `data/ast.jsonl` | AST summaries |
| parse | `data/parse.cache.json` | Parse cache keyed by file hash |
| parse | `data/parse.meta.json` | Parse cache hit/miss metrics |
| extract | `data/events.jsonl` | Graph events (nodes/edges) |
| extract | `data/extract.cache.json` | Extract cache keyed by AST row hash |
| extract | `data/extract.meta.json` | Extract cache hit/miss metrics |
| load | `data/load.state.json` | Incremental load event hashes |
| load | `data/load.meta.json` | Incremental load metrics |
| snapshots | `data/snapshots/*.json` | Snapshot timeline state |
