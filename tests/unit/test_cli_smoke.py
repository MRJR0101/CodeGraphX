from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from codegraphx import __version__
from codegraphx.cli.main import app


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_cli_help_and_version() -> None:
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "CodeGraphX CLI" in help_result.stdout
    assert "enrich" in help_result.stdout
    assert "impact" in help_result.stdout
    assert "snapshots" in help_result.stdout
    assert "doctor" in help_result.stdout

    version_result = runner.invoke(app, ["--version"])
    assert version_result.exit_code == 0
    assert __version__ in version_result.stdout

    enrich_help = runner.invoke(app, ["enrich", "--help"])
    assert enrich_help.exit_code == 0
    assert "Enrichment automation commands" in enrich_help.stdout
    assert "campaign" in enrich_help.stdout
    assert "collectors" in enrich_help.stdout
    assert "intelligence" in enrich_help.stdout
    assert "index-audit" in enrich_help.stdout


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
                "password": "test-password",
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


def test_pipeline_run_skip_load(tmp_path: Path) -> None:
    project_root = tmp_path / "demo"
    (project_root / "pkg").mkdir(parents=True)
    (project_root / "pkg" / "a.py").write_text(
        "def foo():\n    return bar()\n\ndef bar():\n    return 1\n",
        encoding="utf-8",
    )

    projects_yaml = tmp_path / "projects.yaml"
    settings_yaml = tmp_path / "settings.yaml"
    out_dir = tmp_path / "out"

    _write_yaml(
        projects_yaml,
        {"projects": [{"name": "demo", "root": str(project_root), "exclude": []}]},
    )
    _write_yaml(
        settings_yaml,
        {
            "run": {"out_dir": str(out_dir), "max_files": 100, "include_ext": [".py"]},
            "neo4j": {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "test-password",
                "database": "neo4j",
            },
            "meilisearch": {"enabled": False, "host": "localhost", "port": 7700, "index": "codegraphx"},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "pipeline",
            "run",
            "--config",
            str(projects_yaml),
            "--settings",
            str(settings_yaml),
            "--skip-load",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "pipeline complete" in result.stdout
    manifest = out_dir / "pipeline_run_manifest.json"
    assert manifest.exists()
    import json as _json

    data = _json.loads(manifest.read_text(encoding="utf-8"))
    assert data["status"] == "ok"
    stage_names = [s["stage"] for s in data["stages"]]
    assert stage_names == ["scan", "parse", "extract", "load"]
    load_stage = next(s for s in data["stages"] if s["stage"] == "load")
    assert load_stage["status"] == "skipped"


def test_completions_powershell() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["completions", "powershell"])
    assert result.exit_code == 0
    assert "Register-ArgumentCompleter" in result.stdout
    assert "codegraphx" in result.stdout
    assert "'pipeline'" in result.stdout


def test_completions_unknown_shell() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["completions", "tcsh"])
    assert result.exit_code != 0
