# CodeGraphX

CodeGraphX is a multi-phase code intelligence system with AST parsing, architecture graph extraction, code property graph construction, metrics, semantic retrieval, and safe query tooling.

## Current Modules

- `core/` ingestion pipeline and shared models
- `parsers/` tree-sitter parsing
- `extractors/` architecture graph extraction
- `graph/` CPG building and Neo4j writing
- `metrics/` risk and complexity metrics
- `semantic/` embeddings and hybrid retrieval
- `llm/` safe NL-to-Cypher support
- `cli/` command-line entrypoints

## New Platform Scaffold

A production-oriented scaffold now exists in `platform/`:

- contracts and service interfaces
- storage abstractions with in-memory implementation
- quality gate policy
- queue and worker scaffold
- FastAPI app scaffold
- runtime dependency container

See `platform/README.md` for usage details.

<!-- ReadmeForge: The following sections were auto-appended. Move them to the correct position per the 21-section blueprint. -->

## Overview (What & Why)

<!-- TODO: Add a ## Overview section with: what it does, who it is for, and what it does NOT do (prevents wrong-tool confusion). -->


## Use Cases

<!-- TODO: Add a ## Use Cases section with 2-4 bullet points describing concrete scenarios. Example: 'Weekly cleanup of Downloads folder after batch downloads'. -->


## Features / Capabilities

<!-- TODO: Add a ## Features section listing 3-5 key capabilities with bold labels and concrete descriptions. Include design choices like 'zero dependencies' or 'dry-run by default'. -->


## Requirements

- Python 3.8+
- Windows 10/11
- See requirements.txt: tree-sitter, tree-sitter-python, tree-sitter-javascript, neo4j, numpy, sentence-transformers, fastapi, uvicorn, pydantic, click


## Quick Start

<!-- TODO: Add a ## Quick Start section with: 1) cd to project dir, 2) install command if needed, 3) first run command with --help or --dry-run. Use fenced code blocks. -->


## Usage

<!-- TODO: Add a ## Usage section with 2-3 real command examples in fenced code blocks. Show the most common use case first, then advanced options. -->


## Configuration

<!-- TODO: Add a ## Configuration section with a table of env vars, config file paths, or settings with their defaults. -->


## Input / Output

<!-- TODO: Add a ## Input / Output section describing: what files/formats the tool expects, and what files it creates with their locations. -->


## Pipeline Position

<!-- TODO: Add a ## Pipeline Position section with: **Fed by:** (upstream tools) and **Feeds into:** (downstream tools). Optionally add an ASCII flow diagram. -->


## Hardcoded Paths

**Fully parameterized** -- all paths passed via arguments.


## How It Works

<!-- TODO: Add a ## How It Works section with numbered steps describing the internal processing flow from input to output. -->


## Example Output

<!-- TODO: Add a ## Example Output section with a fenced code block showing realistic console output from a typical run. -->


## Files

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 26 | Package initializer |
| `CHANGELOG.md` | 5 | Change history |
| `cli/` | -- |  |
| `codegraphx.egg-info/` | -- |  |
| `CONTRIBUTING.md` | 14 | Markdown document |
| `core/` | -- |  |
| `DoD_CHECKLIST.md` | 281 | Markdown document |
| `extractors/` | -- |  |
| `graph/` | -- |  |
| `justfile` | 30 |  |
| `LICENSE` | 22 | License file |
| `llm/` | -- |  |
| `metrics/` | -- |  |
| `parsers/` | -- |  |
| `platform/` | -- |  |
| `pyproject.toml` | 215 | Project configuration and dependencies |
| `README.md` | 28 | Project documentation |
| `requirements.txt` | 31 | Python dependencies |
| `schema/` | -- |  |
| `semantic/` | -- |  |
| `setup.py` | 33 | Package setup script |
| `src/` | -- | Source code |
| `tests/` | -- | Test suite |
| `uv.lock` | 2535 |  |


## Safety & Reliability

<!-- TODO: Add a ## Safety & Reliability section covering: dry-run mode, backup before destructive operations, resume/checkpoint support, and failure handling behavior. -->


## Logging & Observability

<!-- TODO: Add a ## Logging section describing: where logs are written, log format, verbosity flags, and any run artifacts produced. -->


## Troubleshooting / FAQ

<!-- TODO: Add a ## Troubleshooting section with Problem/Fix pairs for the most common errors. Include known limitations. -->


## Testing

```
python -m pytest tests/ -v
```


## Versioning / Roadmap

<!-- TODO: Add a ## Versioning section with the current version number and a roadmap of planned features. -->


## License & Contact

<!-- TODO: Add a ## License & Contact section with the license name and maintainer contact info. -->
