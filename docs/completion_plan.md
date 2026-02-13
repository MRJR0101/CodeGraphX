# Completion Plan

## Definition of Done

- Lint, types, tests, and build pass.
- Smoke pipeline succeeds in non-DB mode.
- Command docs reflect actual CLI behavior.
- Snapshot/delta workflow verified on changed fixture input.

## Execution Checklist

1. Validate environment
   - `codegraphx doctor --skip-neo4j`

2. Run quality gate
   - `powershell -ExecutionPolicy Bypass -File .\check_project.ps1`

3. Run non-DB smoke
   - `powershell -ExecutionPolicy Bypass -File .\scripts\smoke_no_db.ps1 -ReportPath smoke_no_db_report.json`

4. Run combined release check
   - `powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1`

5. Review generated artifacts
   - `data/*.json*`
   - `smoke_no_db_report.json`

## Failure Handling

- If parse/extract counts regress, inspect `parse.meta.json` and `extract.meta.json`.
- If delta output is empty unexpectedly, verify snapshot inputs and event hash source.
- If load fails, run `doctor` and inspect Neo4j credentials in settings.
