# `codegraphx` Package

This directory contains the canonical Python package for CodeGraphX.

## What Lives Here

- `__main__.py`: packaged CLI entrypoint for `python -m codegraphx`
- `cli/`: Typer command definitions and output helpers
- `core/`: config loading, file IO, snapshots, and pipeline stages
- `graph/`: Neo4j integration and query helpers

## Maintainer Notes

- New runtime behavior should land here, not in the legacy top-level compatibility directories.
- The supported entrypoints are `python -m codegraphx` and the installed `codegraphx` script.
- `cli/main.py` at the repo root exists only as a compatibility shim for older invocations.

For end-user installation and workflow documentation, use the root [`README.md`](../../README.md).
