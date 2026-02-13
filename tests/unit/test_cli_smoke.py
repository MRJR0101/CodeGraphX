from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from codegraphx.cli.main import app


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_cli_help_and_version() -> None:
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "CodeGraphX CLI" in help_result.stdout
    assert "impact" in help_result.stdout
    assert "snapshots" in help_result.stdout
    assert "doctor" in help_result.stdout

    version_result = runner.invoke(app, ["--version"])
    assert version_result.exit_code == 0
    assert "0.2.0" in version_result.stdout


def test_doctor_skip_neo4j(tmp_path: Path) -> None:
    projects_yaml = tmp_path / "projects.yaml"
    settings_yaml = tmp_path / "settings.yaml"

    _write_yaml(projects_yaml, {"projects": []})
    _write_yaml(
        settings_yaml,
        {
            "run": {"out_dir": str(tmp_path / "out"), "max_files": 0, "include_ext": [".py"]},
            "neo4j": {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "codegraphx123",
                "database": "neo4j",
            },
            "meilisearch": {"enabled": False, "host": "localhost", "port": 7700, "index": "codegraphx"},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "doctor",
            "--config",
            str(projects_yaml),
            "--settings",
            str(settings_yaml),
            "--skip-neo4j",
        ],
    )
    assert result.exit_code == 0
    assert "doctor checks" in result.stdout
    assert "neo4j_connection" in result.stdout
    assert "skip" in result.stdout.lower()
