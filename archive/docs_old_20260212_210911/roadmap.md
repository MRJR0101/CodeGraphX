# Roadmap

## Phase 1 — Structural Truth (MVP)
- [x] Directory scaffold
- [ ] Tree-sitter parsing (Python)
- [ ] Extract: top-level functions, classes
- [ ] Extract: IMPORTS, CALLS, INHERITS edges
- [ ] Neo4j loader + schema
- [ ] Duplicate detection (signature hash)
- [ ] CLI: scan, parse, extract, load, analyze

## Phase 2 — Pattern Intelligence
- [ ] AST shape hashing (structure-only, normalized)
- [ ] Token hash (identifiers replaced)
- [ ] Call-chain comparison across projects
- [ ] Plugin pattern cluster detection
- [ ] Fan-in / fan-out metrics
- [ ] READS / WRITES / OVERRIDES edges

## Phase 3 — LLM Interface
- [ ] NL → Cypher translation
- [ ] Subgraph → summary
- [ ] "Explain how X differs from Y" queries
- [ ] Interactive REPL mode
