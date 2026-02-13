# Design

## Objective

CodeGraphX builds a deterministic code knowledge graph from source files, then supports analysis and change comparison.

## Stages

1. `scan`
   - Enumerates source files by extension and exclude rules.
   - Output: `scan.jsonl`.

2. `parse`
   - Parses Python and JS/TS with Tree-sitter-first strategy and fallback parsing.
   - Output: `ast.jsonl`.
   - Cache: `parse.cache.json`, `parse.meta.json`.

3. `extract`
   - Produces graph events for nodes and edges.
   - Emits `CALLS` and `CALLS_FUNCTION` relation edges when available.
   - Output: `events.jsonl`.
   - Cache: `extract.cache.json`, `extract.meta.json`.

4. `load`
   - Incrementally applies events to Neo4j.
   - State: `load.state.json`, `load.meta.json`.

5. `snapshots` + `delta`
   - Snapshot hash timelines for graph state comparison.
   - Works with load-state hashes or direct event hashes.

## Determinism

The pipeline uses stable identities and content hashes to make results reproducible across runs with unchanged inputs.

## Execution Model

- File IO first, DB optional.
- Strong preference for incremental updates over full reloads.
- JSON/JSONL artifacts are first-class audit outputs.
