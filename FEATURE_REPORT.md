# CodeGraphX Feature Report

**Generated:** 2026-02-07  
**Project:** CodeGraphX - Tree-sitter to Code Knowledge Graph Pipeline  
**Version:** 0.1.0

---

## Executive Summary

CodeGraphX is a sophisticated code analysis platform that transforms source code into a knowledge graph using tree-sitter parsing, Neo4j graph database, and comprehensive analysis modules. The system provides CLI-based tools for scanning, parsing, extracting, loading, querying, comparing, searching, and analyzing codebases.

---

## CLI Commands Overview

| Command | Description | Status |
|---------|-------------|--------|
| [`scan`](#scan-command) | Discover projects and enumerate files | ✅ Working |
| [`parse`](#parse-command) | Parse files into lightweight AST summaries | ⚠️ Python 3.13 Issue |
| [`extract`](#extract-command) | Extract semantic facts (nodes/edges) from source files | ⚠️ Parser Dependency |
| [`load`](#load-command) | Load extracted graph events into Neo4j | 🔌 Requires Neo4j |
| [`compare`](#compare-command) | Compare two projects: shared functions, call trees | 🔌 Requires Neo4j |
| [`query`](#query-command) | Run Cypher queries against the graph | 🔌 Requires Neo4j |
| [`search`](#search-command) | Search functions/symbols using MeiliSearch | 🔌 Requires MeiliSearch |
| [`ask`](#ask-command) | Natural language queries about codebase | 🔌 Requires Neo4j + LLM |
| [`analyze`](#analyze-command) | Analysis commands for code quality, hotspots, security | 🔌 Requires Neo4j |

---

## Detailed Feature Specifications

### 1. SCAN Command

**File:** [`src/codegraphx/cli/commands/scan.py`](src/codegraphx/cli/commands/scan.py)

**Purpose:** Discover projects and enumerate files matching configured patterns.

**Options:**
- `--config` (default: `config/projects.yaml`) - Projects config YAML
- `--settings` (default: `config/default.yaml`) - Runtime settings YAML

**Output:**
- Writes `data/scan.jsonl` with file entries containing:
  - `path` - File path
  - `project` - Project name
  - `size` - File size

**Configuration Example:**
```yaml
projects:
  - name: MainScraper
    root: C:/Dev/MainScraper
    exclude:
      - .venv
      - __pycache__
      - node_modules
```

**Supported File Types:**
- `.py` (Python)
- `.js` (JavaScript)
- `.ts` (TypeScript)

---

### 2. PARSE Command

**File:** [`src/codegraphx/cli/commands/parse.py`](src/codegraphx/cli/commands/parse.py)

**Purpose:** Parse files into lightweight AST summaries using tree-sitter.

**Options:**
- `--settings` (default: `config/default.yaml`) - Runtime settings YAML

**Process:**
1. Reads `data/scan.jsonl` to get file list
2. Validates paths against project roots (security)
3. Uses tree-sitter to parse each file
4. Generates AST summaries

**Output:**
- Writes `data/ast.jsonl` containing:
  - `kind` - "ast_summary" or "ast_error"
  - `project` - Project name
  - `path` - File path
  - `root_type` - Root node type (e.g., "module")
  - `bytes` - File size in bytes
  - `error` - Error message if parsing failed

**Security Features:**
- Path validation to prevent directory traversal
- Error message sanitization to prevent information disclosure

**Known Issue:** Requires `tree-sitter-languages` which has Python 3.13 compatibility issues.

---

### 3. EXTRACT Command

**File:** [`src/codegraphx/cli/commands/extract.py`](src/codegraphx/cli/commands/extract.py)

**Purpose:** Extract semantic facts (nodes/edges) from source files.

**Options:**
- `--settings` (default: `config/default.yaml`) - Runtime settings YAML
- `--relations/--no-relations` (default: True) - Extract CALLS and IMPORTS edges

**Extractors:**

#### Python Symbols ([`src/codegraphx/extract/python/symbols.py`](src/codegraphx/extract/python/symbols.py))
Extracts:
- `Function` nodes with properties:
  - `name`, `path`, `start_line`, `end_line`, `params`, `project`
- `Class` nodes with properties:
  - `name`, `path`, `start_line`, `end_line`, `project`
- `Import` nodes
- `Attribute` nodes

#### JavaScript/TypeScript Symbols ([`src/codegraphx/extract/js/symbols.py`](src/codegraphx/extract/js/symbols.py))
Extracts similar symbols for JS/TS files.

#### Relations ([`src/codegraphx/extract/python/relations.py`](src/codegraphx/extract/python/relations.py))
Extracts edges:
- `CALLS` - Function call relationships
- `IMPORTS` - Import/dependency relationships
- `DEFINES` - Symbol definition relationships

**Output:**
- Writes `data/events.jsonl` containing graph events

---

### 4. LOAD Command

**File:** [`src/codegraphx/cli/commands/load.py`](src/codegraphx/cli/commands/load.py)

**Purpose:** Load extracted graph events into Neo4j.

**Options:**
- `--settings` (default: `config/default.yaml`) - Runtime settings YAML

**Process:**
1. Reads `data/events.jsonl`
2. Connects to Neo4j using configured credentials
3. Ensures schema exists (nodes and relationship types)
4. Applies each event to the graph

**Neo4j Schema Created:**
- Nodes: `Function`, `Class`, `Import`, `Attribute`, `Module`
- Relationships: `CALLS`, `IMPORTS`, `DEFINES`

**Configuration:**
```yaml
neo4j:
  uri: ${NEO4J_URI:-bolt://localhost:7687}
  user: ${NEO4J_USER:-neo4j}
  password: ${NEO4J_PASSWORD:-please-change}
  database: neo4j
```

---

### 5. COMPARE Command

**File:** [`src/codegraphx/cli/commands/compare.py`](src/codegraphx/cli/commands/compare.py)

**Purpose:** Compare two projects for shared functions, unique functions, metrics, patterns, and call trees.

**Usage:**
```bash
codegraphx compare <project_a> <project_b> [OPTIONS]
```

**Comparison Modes:**

| Mode | Description |
|------|-------------|
| `shared` | Functions with the same name in both projects |
| `unique-a` | Functions only in project A |
| `unique-b` | Functions only in project B |
| `metrics` | Compare function count, total calls, avg calls/func |
| `patterns` | Compare design pattern counts |
| `calltrees` | Compare call trees for shared functions (depth 3) |

**Example Output (shared functions):**
```
Shared functions between ProjectA and ProjectB: 5

| Function Name | ProjectA Path | ProjectB Path |
|---------------|---------------|---------------|
| add           | a.py:1        | b.py:1        |
| multiply      | -             | b.py:5        |
```

---

### 6. QUERY Command

**File:** [`src/codegraphx/cli/commands/query.py`](src/codegraphx/cli/commands/query.py)

**Purpose:** Run Cypher queries against the graph and print results.

**Usage:**
```bash
codegraphx query "Cypher query or path to .cypher file" [OPTIONS]
```

**Options:**
- `--safe` - Reject write operations for safety

**Safety Features:**
- Validates query length (max 10,000 characters)
- Checks for dangerous keywords in safe mode:
  - `CREATE`, `DELETE`, `DROP`, `SET`, `MERGE`
  - `DETACH`, `REMOVE`, `INDEX`, `CONSTRAINT`, `LOAD CSV`
- Audit logging for all queries

**Example Queries:**

```cypher
// Find all functions in a project
MATCH (f:Function {project: 'MyProject'})
RETURN f.name, f.path, f.start_line

// Find functions calling a specific function
MATCH (caller:Function)-[:CALLS]->(callee:Function {name: 'target_func'})
RETURN caller.name, caller.path

// Find class hierarchy
MATCH (c:Class)-[:DEFINES]->(m:Method)
RETURN c.name, m.name
```

---

### 7. SEARCH Command

**File:** [`src/codegraphx/cli/commands/search.py`](src/codegraphx/cli/commands/search.py)

**Purpose:** Search functions and symbols using MeiliSearch full-text search.

**Usage:**
```bash
codegraphx search <query> [OPTIONS]
```

**Options:**
- `--project` - Filter by project name
- `--index` (default: `all`) - Index to search: all, functions, symbols
- `--limit` (default: 20) - Maximum results

**Configuration:**
```yaml
meilisearch:
  host: ${MEILISEARCH_HOST:-localhost}
  port: ${MEILISEARCH_PORT:-7700}
  index: codegraphx
  enabled: false  # Set to true to enable
```

**Features:**
- Rate limiting (100 requests/minute)
- Project filtering
- Sanitized input for security

---

### 8. ASK Command

**File:** [`src/codegraphx/cli/commands/ask.py`](src/codegraphx/cli/commands/ask.py)

**Purpose:** Natural language queries about your codebase using LLM.

**Usage:**
```bash
codegraphx ask "What does the main function do?" [OPTIONS]
```

**Options:**
- `--project` - Filter by project name
- `--model` (default: `openai`) - LLM provider: openai, anthropic
- `--model-name` (default: `gpt-4o`) - Model name

**Process:**
1. Takes natural language question
2. Uses LLM to translate to Cypher query
3. Executes query against Neo4j
4. Returns results in readable format

**Requirements:**
- Neo4j running with graph data loaded
- OpenAI API key (`OPENAI_API_KEY`) or Anthropic API key (`ANTHROPIC_API_KEY`)
- Install LLM deps: `pip install codegraphx[llm]`

**Example:**
```
Question: In project 'MyProject': What functions call the add function?

Generated Cypher Query:
MATCH (caller:Function)-[:CALLS]->(callee:Function {name: 'add'})
WHERE caller.project = 'MyProject'
RETURN caller.name, caller.path
```

---

### 9. ANALYZE Command

**File:** [`src/codegraphx/cli/commands/analyze.py`](src/codegraphx/cli/commands/analyze.py)

**Purpose:** Comprehensive analysis commands for code quality, hotspots, and security.

**Subcommands:**

#### 9.1 `analyze metrics`
Shows code quality metrics (fan-in, fan-out analysis).

```bash
codegraphx analyze metrics [OPTIONS]
  --project    Filter by project name
  --limit      Result limit (default: 20)
```

**Output:**
- High Fan-Out (Complex Functions) - Functions calling many others
- High Fan-In (Critical Functions) - Functions called by many others

#### 9.2 `analyze hotspots`
Identifies code hotspots (complex, frequently used areas).

```bash
codegraphx analyze hotspots [OPTIONS]
  --project    Filter by project name
```

**Output:**
- Code Quality Score (0-100)
- Most Complex Functions (by line count, params)
- High Dependency Areas (outgoing/incoming deps)

#### 9.3 `analyze security`
Scans for security vulnerabilities.

```bash
codegraphx analyze security [OPTIONS]
  --project    Filter by project name
  --category   Filter by category:
    - sql_injection
    - command_injection
    - hardcoded_secrets
    - insecure_crypto
    - path_traversal
```

**Security Checks ([`src/codegraphx/analysis/security.py`](src/codegraphx/analysis/security.py)):**

| Category | Risk Level | Description |
|----------|------------|-------------|
| SQL Injection | HIGH | Dynamic SQL with string concatenation |
| Command Injection | HIGH | Shell commands with user input |
| Hardcoded Secrets | MEDIUM | API keys, passwords in code |
| Insecure Crypto | MEDIUM | Weak hashing/encryption algorithms |
| Path Traversal | HIGH | File operations with unsanitized paths |

#### 9.4 `analyze debt`
Analyzes technical debt and calculates debt score.

```bash
codegraphx analyze debt [OPTIONS]
  --project    Filter by project name
```

**Output:**
- Debt Score (0-100)
- Debt Level: Excellent / Good / Moderate / High / Critical
- Estimated Hours to Fix
- Debt by Category breakdown
- Top Issues to Address

#### 9.5 `analyze refactor`
Provides refactoring suggestions.

```bash
codegraphx analyze refactor [OPTIONS]
  --project    Filter by project name
  --type       Pattern type:
    - long_function
    - large_class
    - feature_envy
    - data_class
    - high_coupling
```

**Refactoring Patterns Detected:**

| Pattern | Indicator | Suggestion |
|---------|-----------|------------|
| Long Function | >50 lines | Extract to smaller functions |
| Large Class | >300 lines | Split into smaller classes |
| Feature Envy | High calls to other class data | Move method to related class |
| Data Class | No methods, only data | Add behavior or use namedtuple |
| High Coupling | >10 dependencies | Reduce dependencies |

#### 9.6 `analyze duplicates`
Finds duplicate or similar functions using AST hashing.

```bash
codegraphx analyze duplicates [OPTIONS]
  --limit    Result limit (default: 20)
```

**Technique:** AST-based hashing to find syntactically identical functions.

#### 9.7 `analyze patterns`
Detects design patterns in the codebase.

```bash
codegraphx analyze patterns [OPTIONS]
  --type     Pattern type:
    - factories
    - singletons
    - observers
    - repositories
    - plugins
    - all (default)
```

**Design Patterns Detected:**

| Pattern | Characteristics |
|---------|-----------------|
| Factory | Creates objects without specifying exact class |
| Singleton | Single instance with global access |
| Observer | Publish-subscribe notification |
| Repository | Data access layer abstraction |
| Plugin | Dynamic extension system |

#### 9.8 `analyze full`
Runs all analyses and generates comprehensive JSON report.

```bash
codegraphx analyze full [OPTIONS]
  --project    Filter by project name
  --output     Save report to file (JSON)
```

**Report Includes:**
- Timestamp
- Metrics (fan-in, fan-out)
- Hotspot analysis
- Security issues summary
- Technical debt score
- Refactoring suggestions
- Duplicate functions
- Design patterns detected

---

## Analysis Modules

### Core Analysis Files

| Module | Purpose |
|--------|---------|
| [`src/codegraphx/analysis/metrics.py`](src/codegraphx/analysis/metrics.py) | Fan-in/fan-out metrics calculation |
| [`src/codegraphx/analysis/hotspots.py`](src/codegraphx/analysis/hotspots.py) | Hotspot identification and quality scoring |
| [`src/codegraphx/analysis/security.py`](src/codegraphx/analysis/security.py) | Vulnerability scanning |
| [`src/codegraphx/analysis/debt.py`](src/codegraphx/analysis/debt.py) | Technical debt calculation |
| [`src/codegraphx/analysis/refactor.py`](src/codegraphx/analysis/refactor.py) | Refactoring suggestions |
| [`src/codegraphx/analysis/duplicates.py`](src/codegraphx/analysis/duplicates.py) | Duplicate detection via AST hashing |
| [`src/codegraphx/analysis/patterns.py`](src/codegraphx/analysis/patterns.py) | Design pattern detection |
| [`src/codegraphx/analysis/callgraph.py`](src/codegraphx/analysis/callgraph.py) | Call graph analysis |

---

## Security Features

### Path Validation ([`src/codegraphx/core/security.py`](src/codegraphx/core/security.py))

```python
validate_path_within_root(file_path, project_root)
```

Prevents directory traversal attacks by:
1. Resolving absolute paths
2. Checking if path is within project root
3. Rejecting paths outside allowed scope

### Query Safety

```python
_is_safe_query(cypher)  # Checks for dangerous keywords
validate_query_length(cypher)  # Max 10,000 chars
```

### Audit Logging

All operations are logged:
- Event type
- Resource accessed
- Success/failure
- Additional details

### Rate Limiting

Search API limits: 100 requests/minute

---

## Configuration

### Default Configuration (`config/default.yaml`)

```yaml
run:
  out_dir: data
  max_files: 0           # 0 = no limit
  include_ext: [".py", ".js", ".ts"]

neo4j:
  uri: ${NEO4J_URI:-bolt://localhost:7687}
  user: ${NEO4J_USER:-neo4j}
  password: ${NEO4J_PASSWORD:-please-change}
  database: neo4j

meilisearch:
  host: ${MEILISEARCH_HOST:-localhost}
  port: ${MEILISEARCH_PORT:-7700}
  index: codegraphx
  enabled: false
```

### Project Configuration (`config/projects.yaml`)

```yaml
projects:
  - name: ProjectName
    root: /path/to/project
    exclude:
      - .venv
      - __pycache__
      - node_modules
      - dist
      - build
```

---

## Demo Projects

Located in `tests/fixtures/mini_repos/`:

| Project | Files | Content |
|---------|-------|---------|
| `python_pkg_a` | `a.py` | `add()`, `add2()`, `BasePlugin` |
| `python_pkg_b` | `b.py` | `add()`, `multiply()`, `BasePlugin`, `MyPlugin` |

---

## Dependencies

### Core Dependencies
- `typer>=0.12` - CLI framework
- `rich>=13.7` - Rich text output
- `pyyaml>=6.0` - YAML parsing
- `neo4j>=5.22` - Graph database driver
- `httpx>=0.27` - HTTP client
- `tree-sitter>=0.22.3` - AST parsing
- `tree-sitter-languages>=1.10.2` - Language bindings
- `pydantic>=2.7` - Data validation

### Optional LLM Dependencies
- `openai>=1.0` - OpenAI API
- `anthropic>=0.3` - Anthropic API

### Dev Dependencies
- `pytest>=8.2` - Testing
- `ruff>=0.6` - Linting
- `mypy>=1.10` - Type checking

---

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    CodeGraphX Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   SCAN   │ -> │  PARSE   │ -> │ EXTRACT  │ -> │   LOAD   │  │
│  │          │    │          │    │          │    │          │  │
│  │ Discover │    │ AST      │    │ Nodes/   │    │ Neo4j    │  │
│  │ Files    │    │ Summaries│    │ Edges    │    │ Graph    │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│        │              │              │              │           │
│        v              v              v              v           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Neo4j Graph                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          v                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Analysis & Query Commands                  │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────┐  │   │
│  │  │metrics │ │security│ │  debt  │ │patterns│ │search│  │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └──────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Known Issues & Limitations

1. **Python 3.13 Compatibility**: `tree-sitter-languages` has compatibility issues with Python 3.13

2. **Neo4j Required**: Most analysis commands require a running Neo4j instance

3. **MeiliSearch Optional**: Search feature is disabled by default

4. **LLM Dependencies**: Natural language queries require optional LLM dependencies

5. **Limited Language Support**: Currently supports Python, JavaScript, and TypeScript

---

## Windows 11 Compatibility Fixes

The following fixes were applied to ensure Windows 11 compatibility:

1. **Python 3.13 Support**: Updated `pyproject.toml` to support Python 3.13+ by removing the upper bound constraint (`<3.13`)

2. **Unicode Encoding Fix**: Replaced Unicode arrow characters (`→`) with ASCII arrows (`->`) in:
   - [`src/codegraphx/cli/main.py`](src/codegraphx/cli/main.py) - CLI help text
   - [`src/codegraphx/cli/commands/scan.py`](src/codegraphx/cli/commands/scan.py) - Output messages
   - [`src/codegraphx/cli/commands/parse.py`](src/codegraphx/cli/commands/parse.py) - Output messages
   - [`src/codegraphx/cli/commands/load.py`](src/codegraphx/cli/commands/load.py) - Output messages
   - [`src/codegraphx/cli/commands/extract.py`](src/codegraphx/cli/commands/extract.py) - Output messages
   - [`src/codegraphx/llm/summarizers.py`](src/codegraphx/llm/summarizers.py) - Dependency output
   - [`src/codegraphx/reporting/markdown.py`](src/codegraphx/reporting/markdown.py) - Report generation

3. **Path Separator Handling**: The project uses `pathlib.Path` which handles Windows path separators (`\`) correctly

4. **Shell Completion**: The CLI supports PowerShell completions via `codegraphx completions powershell`

---

## Recommendations

1. **Fix Python 3.13 Compatibility**: Update tree-sitter dependencies or switch to tree-sitter directly
2. **Add More Languages**: Implement extractors for Go, Rust, Java, C/C++, C#
3. **Improve Performance**: Add parallel processing for large codebases
4. **Web UI**: Consider adding a web interface for visualization
5. **CI/CD Integration**: Add GitHub Actions/GitLab CI integration

---

## Report Generated By

CodeGraphX Feature Analysis System  
Analyzed all CLI commands, analysis modules, and configuration files.
