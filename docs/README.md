# CodeGraphX Documentation

This directory contains the maintained project documentation for the public repo.

## Start Here

- [`commands.md`](commands.md): CLI command reference and examples
- [`design.md`](design.md): pipeline stages, execution model, and artifacts
- [`schema.md`](schema.md): graph entities, identities, and relationships
- [`queries.md`](queries.md): common Cypher usage patterns
- [`security-architecture.md`](security-architecture.md): security model and safeguards
- [`roadmap.md`](roadmap.md): planned work
- [`completion_plan.md`](completion_plan.md): contributor execution checklist

## Suggested Reading Order

1. Read the root [`README.md`](../README.md) for installation and quick start.
2. Read [`commands.md`](commands.md) for CLI usage.
3. Read [`design.md`](design.md) and [`schema.md`](schema.md) if you are changing pipeline behavior.
4. Read [`security-architecture.md`](security-architecture.md) before changing query execution or loading behavior.

## Validation

For current validation guidance, see [`VERIFY.md`](../VERIFY.md).

Typical commands:

```bash
python -m pytest -q
python -m codegraphx --help
```

For the full Windows release gate:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```
