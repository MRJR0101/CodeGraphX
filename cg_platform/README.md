# CodeGraphX Platform Scaffold

This scaffold turns the existing analysis engine into a platform-ready shape.

## Added Layers

- `platform/contracts.py`
  - Service contracts and request/response models.
- `platform/storage/`
  - Repository interfaces plus in-memory implementation.
- `platform/services.py`
  - Ingestion and query services backed by `IngestionPipeline`.
- `platform/policy/`
  - Quality gate policy for CI/deployment checks.
- `platform/jobs/`
  - Queue and worker stubs for async ingestion.
- `platform/api/`
  - FastAPI app factory and routes.
- `platform/runtime.py`
  - Dependency wiring container.

## Quick Start

```python
from codegraphx.cg_platform import build_runtime
from codegraphx.cg_platform.contracts import IngestionRequest

runtime = build_runtime()
record = runtime.ingestion_service.ingest(
    IngestionRequest(repo_path="C:/path/to/repo")
)
print(record.status, record.summary)
```

## API Start (optional)

```python
from codegraphx.cg_platform.api import create_app
app = create_app()
```

Run with:

```bash
uvicorn codegraphx.cg_platform.api.app:create_app --factory --reload
```

## Notes

- The scaffold is additive. Existing CLI and pipeline behavior remain unchanged.
- In-memory storage and queue are intended for local use; replace with persistent backends for production.

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
- Third-party: codegraphx, fastapi, pydantic


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
