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
powershell -ExecutionPolicy RemoteSigned -File .\scripts\release_check.ps1
```

<!-- ReadmeForge: The following sections were auto-appended. Move them to the correct position per the 21-section blueprint. -->

## Overview (What & Why)

<!-- TODO: Add a ## Overview section with: what it does, who it is for, and what it does NOT do (prevents wrong-tool confusion). -->


## Use Cases

<!-- TODO: Add a ## Use Cases section with 2-4 bullet points describing concrete scenarios. Example: 'Weekly cleanup of Downloads folder after batch downloads'. -->


## Features / Capabilities

<!-- TODO: Add a ## Features section listing 3-5 key capabilities with bold labels and concrete descriptions. Include design choices like 'zero dependencies' or 'dry-run by default'. -->


## Quick Start

<!-- TODO: Add a ## Quick Start section with: 1) cd to project dir, 2) install command if needed, 3) first run command with --help or --dry-run. Use fenced code blocks. -->


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
| `commands.md` | 147 | Markdown document |
| `completion_plan.md` | 33 | Markdown document |
| `design.md` | 41 | Markdown document |
| `queries.md` | 59 | Markdown document |
| `README.md` | 41 | Project documentation |
| `roadmap.md` | 24 | Markdown document |
| `schema.md` | 43 | Markdown document |
| `security-architecture.md` | 30 | Markdown document |


## Safety & Reliability

<!-- TODO: Add a ## Safety & Reliability section covering: dry-run mode, backup before destructive operations, resume/checkpoint support, and failure handling behavior. -->


## Logging & Observability

<!-- TODO: Add a ## Logging section describing: where logs are written, log format, verbosity flags, and any run artifacts produced. -->


## Troubleshooting / FAQ

<!-- TODO: Add a ## Troubleshooting section with Problem/Fix pairs for the most common errors. Include known limitations. -->


## Versioning / Roadmap

<!-- TODO: Add a ## Versioning section with the current version number and a roadmap of planned features. -->


## License & Contact

<!-- TODO: Add a ## License & Contact section with the license name and maintainer contact info. -->

