# CodeGraphX Completion Plan

## Executive Summary

**Recommendation: Single-Person Developer, Optimize for Speed + Maintainability**

The goal is a code intelligence tool that:
- Extracts semantic facts from code using Tree-sitter
- Stores them in Neo4j for querying
- Provides duplicate detection, pattern discovery, and cross-project comparison

---

## The Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RECOMMENDED STACK                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tree-sitter      →     Events (JSONL)     →     Neo4j          │
│  (fast parsing)         (versioned schema)         (graph queries)│
│                                                                 │
│                               ↓                                  │
│                        (Optional) Search Index                   │
│                        Meilisearch/Typesense/OpenSearch          │
│                        - Fast text & fuzzy lookup                │
│                        - Filters, facets                         │
│                        - Avoids Neo4j for "find files with X"   │
│                                                                 │
│  CLI (Typer)            Python                    OpenAI API     │
│  (simple interface)     (maintainable)             (future)       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Stack?

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Parser** | Tree-sitter | Fast, deterministic, multi-language support |
| **Intermediate** | JSONL | Debug-able, replay-able, versioned schema |
| **Graph DB** | **Neo4j** | Mature, Cypher support, enterprise-ready |
| **Search Index** | Optional | Meilisearch/Typesense for fast text search |
| **CLI** | Typer + Rich | Python-native, excellent DX |
| **Language** | Python | Already used, good ecosystem |
| **LLM** | OpenAI (later) | Simple API, can switch later |

---

## Versioned JSONL Schema

**Critical for future-proofing:**

```json
{
  "event_type": "node|edge|error",
  "schema_version": "1.0.0",
  "producer": {
    "name": "codegraphx",
    "version": "0.1.0"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "label": "Function",
    "uid": "abc123...",
    "stable_ids": {
      "file_id": "sha256:file_hash",
      "symbol_id": "sha256:content_hash",
      "span_id": "line_start:line_end"
    },
    "repo": {
      "revision": "abc123def",
      "path": "src/main.py"
    },
    "props": {
      "name": "process_data",
      "arity": 2
    }
  }
}
```

**Schema Fields Explained:**

| Field | Purpose |
|-------|---------|
| `event_type` | Node, edge, or error event |
| `schema_version` | For backward/forward compatibility |
| `producer_version` | Which extractor version created this |
| `timestamp` | When event was created |
| `stable_ids.file_id` | SHA256 hash of file content |
| `stable_ids.symbol_id` | SHA256 hash of symbol definition |
| `stable_ids.span_id` | Line range for location |
| `repo.revision` | Git commit SHA for reproducibility |
| `repo.path` | Relative file path |

---

## Phase-by-Phase Plan

### Phase 1: Core Extraction (COMPLETED ✅)

**Goal:** Complete Python extraction, add JavaScript support

**Completed:**
- ✅ CALLS edges extraction (function → function calls)
- ✅ IMPORTS edges extraction (module dependencies)
- ✅ JavaScript/TypeScript extraction module
- ✅ Tree-sitter queries for calls and imports
- ✅ Config updated for .py, .js, .ts extensions
- ✅ Versioned JSONL schema (with stable IDs)

**Files Modified:**
- `src/codegraphx/extract/python/relations.py` - CALLS, IMPORTS
- `src/codegraphx/extract/js/symbols.py` - JS/TS extraction (NEW)
- `src/codegraphx/parsing/treesitter/queries/python/calls.scm` - Queries
- `src/codegraphx/parsing/treesitter/queries/python/imports.scm` - Queries
- `src/codegraphx/cli/commands/extract.py` - Multi-language support
- `config/default.yaml` - Added .js, .ts extensions

---

### Phase 2: Neo4j Backend (COMPLETED ✅)

**Goal:** Efficient graph loading and querying

**Completed:**
- ✅ Neo4jLoader with MERGE semantics (upsert)
- ✅ Constraints and indexes for performance
- ✅ Batch loading support

**Files Modified:**
- `src/codegraphx/graph/neo4j/loader.py` - Enhanced loader
- `src/codegraphx/cli/commands/load.py` - Backend selection

---

### Phase 3: Analysis & Patterns (NEXT)

**Goal:** Duplicate detection, pattern discovery, metrics

#### 3.1 AST Shape Hashing

**Purpose:** Detect duplicate code even when variable names differ

**Implementation:**
```python
# src/codegraphx/analysis/ast_hashing.py
def ast_shape_hash(node: Node) -> str:
    """Normalize AST and compute hash."""
    normalized = normalize_ast(node)  # Replace identifiers with placeholders
    return sha256(normalized.encode()).hexdigest()
```

**Deliverable:** `codegraphx analyze ast-similar --threshold 0.8`

#### 3.2 Fan-in/Fan-out Metrics

**Purpose:** Identify highly connected functions (complexity) and heavily-used functions (dependencies)

**Cypher Queries:**
```cypher
-- High fan-out (calls many functions)
MATCH (f:Function)-[:CALLS]->(c:Function)
RETURN f.name, count(c) as fan_out
ORDER BY fan_out DESC
LIMIT 20

-- High fan-in (called by many functions)
MATCH (c:Function)<-[:CALLS]-(f:Function)
RETURN c.name, count(f) as fan_in
ORDER BY fan_in DESC
LIMIT 20
```

**Deliverable:** `codegraphx analyze metrics --project MyProject`

#### 3.3 Pattern Detection

**Purpose:** Identify design patterns (Factory, Singleton, Observer, Plugin)

**Approach:** Cypher pattern matching

```cypher
-- Factory pattern: classes with create/new methods returning same type
MATCH (factory:Class)-[:CONTAINS]->(create_fn:Function)
MATCH (create_fn)-[:CALLS]->(product:Class)
WHERE create_fn.name CONTAINS 'create' OR create_fn.name CONTAINS 'new'
RETURN factory.name, collect(product.name) as products
```

**Deliverable:** `codegraphx analyze patterns --type factory`

---

### Phase 4: Cross-Project Comparison

**Goal:** Compare codebases for refactoring, migration, duplication

#### 4.1 Shared Function Detection

**Purpose:** Find duplicate functions across projects

**Cypher:**
```cypher
MATCH (f1:Function {project: 'ProjectA'})
MATCH (f2:Function {project: 'ProjectB'})
WHERE f1.name = f2.name AND f1.signature_hash = f2.signature_hash
RETURN f1.name, f1.path as path_a, f2.path as path_b
```

**Deliverable:** `codegraphx compare ProjectA ProjectB --shared-functions`

#### 4.2 Call Tree Diff

**Purpose:** Compare how similar functions are implemented

```cypher
-- Get call trees for same function in different projects
MATCH (f1:Function {project: 'ProjectA', name: $fn_name})
MATCH (f2:Function {project: 'ProjectB', name: $fn_name})
OPTIONAL MATCH path1 = (f1)-[:CALLS*1..5]->()
OPTIONAL MATCH path2 = (f2)-[:CALLS*1..5]->()
RETURN f1.name, length(path1) as calls_a, length(path2) as calls_b
```

**Deliverable:** `codegraphx compare ProjectA ProjectB --diff function_name`

---

### Phase 5: Optional Search Index (Future)

**Goal:** Fast text and fuzzy lookup at scale

#### 5.1 Why Add a Search Index?

Neo4j is great for relationships, but **not optimized for:**
- Full-text search across files
- Fuzzy matching ("seach" → "search")
- Filtering by file type, author, date
- Faceted search

#### 5.2 Recommended Options

| Option | Pros | Cons |
|--------|------|------|
| **Meilisearch** | Fastest, typo-tolerant, easy | Smaller community |
| **Typesense** | Great typo tolerance, self-hosted | Less mature |
| **OpenSearch** | Enterprise, features | Complex setup |

#### 5.3 Architecture

```
JSONL Events → Neo4j (relationships)
              ↓
         Search Index
         - Function names
         - File contents (optional)
         - Symbol definitions
         - Docstrings/comments
```

#### 5.4 Sync Strategy

```python
# src/codegraphx/indexing/sync.py
def sync_to_search_index(events, index_client):
    """Sync extracted events to search index."""
    for event in events:
        if event.event_type == "node":
            doc = {
                "id": event.data.uid,
                "type": event.data.label,
                "name": event.data.props.get("name"),
                "file": event.data.repo.path,
                "content": extract_snippet(event.data.repo.path, event.data.span_id)
            }
            index_client.index_document(doc)
```

**Deliverable:** `codegraphx search "function_name" --fuzzy`

---

### Phase 6: LLM Interface

**Goal:** Natural language queries against the codebase

#### 6.1 NL → Cypher Translation

**Purpose:** Convert "Find all functions that call X" to Cypher

**Implementation:**
```python
# src/codegraphx/llm/cypher_prompting.py
def translate_nl_to_cypher(question: str, schema: str) -> str:
    """Use LLM to convert natural language to Cypher."""
    prompt = f"""
    You are a code analysis assistant. Convert this question to Cypher.

    Graph Schema:
    {schema}

    Question: {question}

    Return only the Cypher query, nothing else.
    """
    return openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content
```

#### 6.2 Graph → Summary

**Purpose:** Explain code patterns in human-readable form

```python
def summarize_subgraph(nodes: list, edges: list) -> str:
    """Use LLM to summarize a subgraph."""
    # Serialize graph to text
    graph_text = serialize_graph(nodes, edges)
    prompt = f"Summarize this code structure: {graph_text}"
    return llm.generate(prompt)
```

**Deliverable:** `codegraphx query "find all database connections"` → Natural response

#### 6.3 Interactive REPL

**Purpose:** Shell-like interface for exploration

```bash
$ codegraphx repl
codegraphx> find functions that call 'validate'
Found 3 functions:
  - UserValidator.validate_email (line 42)
  - OrderProcessor.validate_payment (line 78)
  - FormHandler.validate_input (line 134)

codegraphx> show call graph for UserValidator
[displays graph]
```

---

## Immediate Next Steps (Week 1)

1. **Test Phase 1-2:**
   ```bash
   codegraphx scan
   codegraphx extract --relations
   codegraphx load --backend neo4j
   codegraphx analyze duplicates
   ```

2. **Start Phase 3:**
   - Implement AST shape hashing
   - Add fan-in/fan-out CLI commands
   - Create pattern detection queries

---

## Files Changed Summary

| Phase | Files |
|-------|-------|
| Phase 1 | `extract/python/relations.py`, `extract/js/symbols.py`, `calls.scm`, `imports.scm` |
| Phase 2 | `graph/neo4j/loader.py`, `cli/commands/load.py` |
| Phase 3 | `analysis/ast_hashing.py`, `analysis/metrics.py`, enhance `analysis/patterns.py` |
| Phase 4 | Enhance `analysis/callgraph.py`, `cli/commands/compare.py` |
| Phase 5 | `indexing/sync.py`, `indexing/meilisearch.py` (future) |
| Phase 6 | `llm/cypher_prompting.py`, `llm/summarizer.py`, `cli/repl.py` |

---

## Dependencies

```bash
pip install neo4j>=5.22  # Already included
# Future Phase 5-6:
pip install meilisearch  # Optional search index
pip install openai>=1.0  # For LLM features
```

---

## Success Criteria

After all phases, CodeGraphX should:

- [x] Extract Python + JavaScript with all edges (CONTAINS, CALLS, IMPORTS, INHERITS)
- [x] Versioned JSONL schema (future-proof)
- [x] Load 10K files in < 10 minutes
- [ ] Query call graphs with < 1 second latency
- [ ] Detect duplicates with > 80% precision
- [ ] Fast text search (Phase 5, optional)
- [ ] Answer "find functions calling X" in natural language (Phase 6)
- [ ] Compare two codebases with shared function analysis (Phase 4)
