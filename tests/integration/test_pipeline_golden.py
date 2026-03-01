from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from codegraphx.core.config import load_projects, load_settings
from codegraphx.core.io import read_json, read_jsonl
from codegraphx.core.stages import run_extract, run_parse, run_scan


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_pipeline_golden_mini_repos(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixtures = repo_root / "tests" / "fixtures" / "mini_repos"
    out_dir = tmp_path / "out"

    projects_yaml = tmp_path / "projects.yaml"
    settings_yaml = tmp_path / "settings.yaml"

    _write_yaml(
        projects_yaml,
        {
            "projects": [
                {
                    "name": "DemoA",
                    "root": str(fixtures / "python_pkg_a"),
                    "exclude": [".venv", "__pycache__"],
                },
                {
                    "name": "DemoB",
                    "root": str(fixtures / "python_pkg_b"),
                    "exclude": [".venv", "__pycache__"],
                },
            ]
        },
    )
    _write_yaml(
        settings_yaml,
        {
            "run": {"out_dir": str(out_dir), "max_files": 0, "include_ext": [".py"]},
            "neo4j": {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "test-password",
                "database": "neo4j",
            },
            "meilisearch": {"enabled": False, "host": "localhost", "port": 7700, "index": "codegraphx"},
        },
    )

    projects = load_projects(projects_yaml)
    settings = load_settings(settings_yaml)

    _, scan_count = run_scan(projects, settings)
    _, parse_count = run_parse(settings)
    _, event_count = run_extract(settings, relations=True)

    assert scan_count == 2
    assert parse_count == 2
    assert event_count == 20

    scan_rows = read_jsonl(out_dir / "scan.jsonl")
    assert all(".venv" not in row["path"] for row in scan_rows)
    assert all("__pycache__" not in row["path"] for row in scan_rows)

    ast_rows = read_jsonl(out_dir / "ast.jsonl")
    fn_names = sorted(fn["name"] for row in ast_rows for fn in row["functions"])
    assert fn_names == ["add", "add", "add2", "multiply", "run", "run", "run"]

    events = read_jsonl(out_dir / "events.jsonl")
    edge_types = sorted({row["type"] for row in events if row.get("kind") == "edge"})
    assert edge_types == ["CONTAINS", "DEFINES"]
    extract_meta_first = read_json(out_dir / "extract.meta.json")
    assert extract_meta_first["rows_total"] == 2
    assert extract_meta_first["cache_hits"] == 0
    assert extract_meta_first["cache_misses"] == 2
    assert extract_meta_first["events_total"] == 20

    parse_meta_first = read_json(out_dir / "parse.meta.json")
    assert parse_meta_first["files_total"] == 2
    assert parse_meta_first["cache_hits"] == 0
    assert parse_meta_first["cache_misses"] == 2

    _, parse_count_2 = run_parse(settings)
    assert parse_count_2 == 2
    parse_meta_second = read_json(out_dir / "parse.meta.json")
    assert parse_meta_second["files_total"] == 2
    assert parse_meta_second["cache_hits"] == 2
    assert parse_meta_second["cache_misses"] == 0

    _, event_count_2 = run_extract(settings, relations=True)
    assert event_count_2 == 20
    extract_meta_second = read_json(out_dir / "extract.meta.json")
    assert extract_meta_second["rows_total"] == 2
    assert extract_meta_second["cache_hits"] == 2
    assert extract_meta_second["cache_misses"] == 0
    assert extract_meta_second["events_total"] == 20

