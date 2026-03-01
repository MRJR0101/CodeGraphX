# CodeGraphX Documentation

This directory contains the current docs for CodeGraphX 0.2.0.

## Compatibility

- Python: 3.10 to 3.13
- Neo4j: 5.x
- OS: Windows and Linux

## Document Map

- `commands.md`: CLI reference and examples
- `design.md`: architecture and stage internals
- `schema.md`: graph model and event identities
- `queries.md`: common Cypher and usage patterns
- `security-architecture.md`: security model and hardening notes
- `roadmap.md`: near-term and medium-term milestones
- `completion_plan.md`: practical execution checklist for contributors

## Fast Start

1. Copy `config/projects.example.yaml` to `config/projects.yaml`, then update roots.
2. Confirm `config/default.yaml` values.
3. Run:
   - `codegraphx scan`
   - `codegraphx parse`
   - `codegraphx extract`
4. Optional:
   - `codegraphx load` (Neo4j)
   - `codegraphx snapshots create`
   - `codegraphx delta <old> <new>`

## Validation

Use one command to run the full project gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```
