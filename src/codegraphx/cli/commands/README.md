# CLI Commands

Command modules under this directory are wired by `src/codegraphx/cli/main.py` and exposed through:

```powershell
uv run codegraphx --help
```

## Command Surface

- `scan`
  - Reads projects/settings YAML and writes `scan.jsonl` metadata output.
- `parse`
  - Parses scan output into normalized AST artifacts.
- `extract`
  - Extracts graph-ready entities and relations from parsed artifacts.
- `load`
  - Loads extracted graph data into configured graph backend.
- `query`
  - Executes graph queries and prints tabular results.
- `search`
  - Runs semantic/text search over indexed project data.
- `ask`
  - Convenience NL query interface over indexed project context.
- `compare`
  - Compares two snapshot artifacts and reports differences.
- `doctor`
  - Validates local runtime configuration and connectivity.
- `impact`
  - Estimates change impact from symbols/files to downstream call graph areas.
- `delta`
  - Computes and reports change delta between snapshots.
- `snapshots` (command group)
  - Subcommands for snapshot creation/listing/comparison flows.
- `analyze` (command group)
  - Aggregated analysis/reporting subcommands.
- `enrich` (command group)
  - Wrappers over enrichment utilities (`backlog`, `chunk-scan`, `campaign`, `index-audit`, `collectors`, `intelligence`).

## Typical Pipeline

```powershell
uv run codegraphx scan --config .\config\projects.yaml --settings .\config\default.yaml
uv run codegraphx parse --settings .\config\default.yaml
uv run codegraphx extract --settings .\config\default.yaml
uv run codegraphx load --settings .\config\default.yaml
```

## Validation and Troubleshooting

```powershell
uv run codegraphx doctor --config .\config\projects.yaml --settings .\config\default.yaml --skip-neo4j
uv run codegraphx --version
```

## Notes

- Commands are parameterized via CLI options and YAML configs; no hardcoded project paths are required.
- For large-scale enrichment workflows, use scripts in `scripts/` (`chunked_scan_enrich.py`, `enrichment_campaign.py`) on top of these core commands.
