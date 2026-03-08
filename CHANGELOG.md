# Changelog

## Unreleased

- Cleaned the public repo by removing recovered duplicate content, local-only configs, and report artifacts.
- Aligned package metadata, dependency declarations, and contributor setup instructions.
- Fixed project-aware search and impact behavior for file nodes without explicit `project` properties.
- Added stale-record deletion support to incremental Neo4j loads.
- Replaced stale validation snapshots with current verification guidance.

## 0.2.0

- Added the canonical `src/codegraphx` package layout and Typer-based CLI entrypoint.
- Shipped deterministic scan, parse, extract, load, snapshot, delta, and analysis workflows.
- Added optional Neo4j integration plus no-database JSONL-first operation.
- Added CI, linting, typing, and test automation for the packaged CLI.

## 0.1.0

- Initial project scaffolding.
