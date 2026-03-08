# Roadmap

## Recently Completed

- Parser modules extracted from `stages.py` into `core/parsers/` package
  (`python.py`, `javascript.py`). `stages.py` is now thin orchestration only.
- SQLite FTS5 search index (`search.db`) built by `load`, queried by `search`.
  Falls back gracefully to O(n) JSONL scan before first load.
- `analyze hotspots` and `analyze metrics` fixed to use `CALLS_FUNCTION` edges
  for accurate fan-in/fan-out coupling metrics.
- `start-neo4j.ps1` Docker helper script. Reads credentials from `.env`,
  creates or restarts `neo4j-cgx`, polls until bolt is ready.
- AST nested function scope handling fixed to match tree-sitter behavior.
- `_looks_write_query` false-positive guard replaced with regex clause boundaries.
- `_resolve_query` restricted to `.cypher` files (closed arbitrary file read).

## Next Milestones

1. Data Quality
   - Expand parser coverage for class and method constructs in JS/TS.
   - Add fixture sets for mixed-language monorepos.
   - Add TypeScript-specific type annotation extraction.

2. Analysis Depth
   - Add path-sensitive impact scoring.
   - Add churn-aware hotspot ranking from VCS metadata.
   - Wire `ask` command to a real LLM backend.

3. Scale
   - Add chunked parallel extract/load execution.
   - Add memory-bound streaming for large repos.

4. Developer Experience
   - Add `codegraphx pipeline run` orchestration command.
   - Add machine-readable run manifest for every stage.
   - Add shell completion generation for PowerShell and bash.

5. Governance
   - Expand threat model and security test fixtures.
   - Add compatibility matrix documentation for Python/OS combinations.
   - Add integration test suite for Neo4j-backed commands.
