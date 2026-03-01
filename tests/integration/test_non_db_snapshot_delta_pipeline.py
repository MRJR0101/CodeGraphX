from __future__ import annotations

import shutil
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from codegraphx.cli.main import app
from codegraphx.core.config import load_projects, load_settings
from codegraphx.core.io import read_json
from codegraphx.core.snapshots import list_snapshots
from codegraphx.core.stages import run_extract, run_parse, run_scan


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_non_db_snapshot_delta_pipeline(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixtures = repo_root / "tests" / "fixtures" / "mini_repos"
    copied = tmp_path / "repos"
    shutil.copytree(fixtures, copied)

    out_dir = tmp_path / "out"
    projects_yaml = tmp_path / "projects.yaml"
    settings_yaml = tmp_path / "settings.yaml"

    _write_yaml(
        projects_yaml,
        {
            "projects": [
                {
                    "name": "DemoA",
                    "root": str(copied / "python_pkg_a"),
                    "exclude": [".venv", "__pycache__"],
                },
                {
                    "name": "DemoB",
                    "root": str(copied / "python_pkg_b"),
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
    _, extract_count = run_extract(settings, relations=True)
    assert scan_count == 2
    assert parse_count == 2
    assert extract_count > 0

    runner = CliRunner()
    old_create = runner.invoke(
        app,
        ["snapshots", "create", "--settings", str(settings_yaml), "--label", "old"],
    )
    assert old_create.exit_code == 0
    assert "hash_source" in old_create.stdout
    assert "events" in old_create.stdout

    target = copied / "python_pkg_a" / "a.py"
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\ndef subtract(a, b):\n    return a - b\n",
        encoding="utf-8",
    )

    run_scan(projects, settings)
    run_parse(settings)
    run_extract(settings, relations=True)

    new_create = runner.invoke(
        app,
        ["snapshots", "create", "--settings", str(settings_yaml), "--label", "new"],
    )
    assert new_create.exit_code == 0

    snaps = list_snapshots(settings)
    old_id = next(p.stem for p in snaps if p.stem.endswith("-old"))
    new_id = next(p.stem for p in snaps if p.stem.endswith("-new"))

    report_json = tmp_path / "delta_report.json"
    delta_result = runner.invoke(
        app,
        [
            "delta",
            old_id,
            new_id,
            "--settings",
            str(settings_yaml),
            "--output",
            str(report_json),
            "--show-lists",
        ],
    )
    assert delta_result.exit_code == 0

    report = read_json(report_json)
    counts = report.get("counts", {})
    assert isinstance(counts, dict)
    assert int(counts.get("added", 0)) > 0 or int(counts.get("changed", 0)) > 0

    changed_functions = report.get("changed_functions", [])
    assert isinstance(changed_functions, list)
    assert any(row.get("function") == "subtract" for row in changed_functions if isinstance(row, dict))

