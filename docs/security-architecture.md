# Security Architecture

## Scope

CodeGraphX runs local parsing, local artifact generation, and optional Neo4j connectivity.

## Security Controls

- Parameterized Cypher in command paths that consume user input.
- Read-only guard option for ad-hoc query execution (`query --safe`).
- Incremental processing with deterministic hashing to reduce risky ad-hoc script edits.
- Local config supports environment-variable secrets (`${ENV_VAR:-default}`).

## Operational Guidance

- Keep credentials in environment variables, not committed files.
- Treat generated reports as build artifacts.
- Restrict DB network exposure to trusted interfaces.
- Use least-privilege DB credentials for analysis workloads.

## Known Limits

- `query` accepts raw Cypher; `--safe` is lexical and intentionally conservative.
- LLM-backed workflows can generate broad queries and should be reviewed.

## Recommended Checks

- Run `codegraphx doctor` before DB-backed operations.
- Run `scripts/release_check.ps1` before shipping changes.
