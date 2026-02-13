from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from codegraphx.core.config import load_projects, load_settings
from codegraphx.core.io import read_jsonl
from codegraphx.core.stages import run_extract, run_parse, run_scan


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_extract_emits_calls_function_edges(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "mod.py").write_text(
        "def b():\n"
        "    return 1\n\n"
        "def c():\n"
        "    return b()\n",
        encoding="utf-8",
    )

    projects_yaml = tmp_path / "projects.yaml"
    settings_yaml = tmp_path / "settings.yaml"
    out_dir = tmp_path / "out"

    _write_yaml(projects_yaml, {"projects": [{"name": "R", "root": str(repo), "exclude": []}]})
    _write_yaml(
        settings_yaml,
        {
            "run": {"out_dir": str(out_dir), "max_files": 0, "include_ext": [".py"]},
            "neo4j": {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "codegraphx123",
                "database": "neo4j",
            },
            "meilisearch": {"enabled": False, "host": "localhost", "port": 7700, "index": "codegraphx"},
        },
    )

    projects = load_projects(projects_yaml)
    settings = load_settings(settings_yaml)

    run_scan(projects, settings)
    run_parse(settings)
    run_extract(settings, relations=True)

    events = read_jsonl(out_dir / "events.jsonl")
    calls_function = [e for e in events if e.get("kind") == "edge" and e.get("type") == "CALLS_FUNCTION"]
    assert calls_function, "expected at least one CALLS_FUNCTION edge"

    calls_symbol = [e for e in events if e.get("kind") == "edge" and e.get("type") == "CALLS"]
    assert calls_symbol, "expected at least one CALLS edge"

