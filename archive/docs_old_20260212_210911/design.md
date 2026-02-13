# Design Notes (MVP)

## Pipeline
scan → parse → extract → load → analyze

## Key Principle
Store deterministic facts (nodes/edges as JSONL) before any DB/LLM.

## Phases
1. **Structural Truth** — Tree-sitter → facts → Neo4j (no AI)
2. **Pattern Intelligence** — AST hashing, call-chain comparison, plugin detection
3. **LLM Interface** — NL → Cypher, graph → summaries (last step)
