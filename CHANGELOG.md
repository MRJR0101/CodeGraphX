# Changelog

## 0.2.0 - 2026-02-13

- Added incremental extract caching with metadata output.
- Added incremental Neo4j load with persisted load state and load metrics.
- Added snapshot timeline workflow (`snapshots list/create/diff/report`).
- Added `delta` command for snapshot-to-snapshot change summaries.
- Added `impact` command with transitive caller traversal.
- Hardened Cypher execution paths with query parameterization.
- Added no-DB snapshot hashing fallback from `events.jsonl`.
- Added non-DB end-to-end smoke automation (`scripts/smoke_no_db.ps1`).
- Added CI no-DB smoke job.
