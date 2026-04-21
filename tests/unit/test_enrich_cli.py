"""Unit tests for the enrich CLI subcommands.

The enrich subcommands are thin argv assemblers that forward to external
scripts via ``_run_script``. These tests patch ``_run_script`` to capture
the assembled args without actually running uv/subprocess, which gives
deterministic coverage of every flag branch.
"""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from codegraphx.cli.commands import enrich as enrich_mod
from codegraphx.cli.main import app


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_script(script_name: str, args: list[str]) -> None:
        calls.append((script_name, list(args)))

    monkeypatch.setattr(enrich_mod, "_run_script", fake_run_script)
    return calls


def _invoke(args: list[str]) -> Any:
    runner = CliRunner()
    return runner.invoke(app, args)


def test_backlog_minimal(captured: list[tuple[str, list[str]]]) -> None:
    result = _invoke(["enrich", "backlog", "--db", "db.sqlite"])
    assert result.exit_code == 0, result.stdout
    assert captured[0][0] == "enrichment_backlog.py"
    argv = captured[0][1]
    assert "--db" in argv and "db.sqlite" in argv
    assert "--limit" in argv


def test_backlog_all_flags(captured: list[tuple[str, list[str]]]) -> None:
    result = _invoke(
        [
            "enrich",
            "backlog",
            "--db",
            "db.sqlite",
            "--limit",
            "7",
            "--min-lines",
            "100",
            "--root-prefix",
            "C:/src",
            "--include-enriched",
            "--json",
            "--output",
            "out.json",
        ]
    )
    assert result.exit_code == 0
    argv = captured[0][1]
    assert "--root-prefix" in argv
    assert "--include-enriched" in argv
    assert "--json" in argv
    assert "--output" in argv


def test_chunk_scan_all_flags(captured: list[tuple[str, list[str]]]) -> None:
    result = _invoke(
        [
            "enrich",
            "chunk-scan",
            "--target-root",
            "C:/src",
            "--chunk-size",
            "4",
            "--tag",
            "t1",
            "--exclude",
            "foo,bar",
            "--max-projects",
            "10",
            "--update-db",
            "db.sqlite",
            "--source-project",
            "src",
            "--resume",
            "--dry-run",
        ]
    )
    assert result.exit_code == 0
    script, argv = captured[0]
    assert script == "chunked_scan_enrich.py"
    for flag in ("--tag", "--exclude", "--max-projects", "--update-db", "--source-project", "--resume", "--dry-run"):
        assert flag in argv


def test_campaign_all_flags(captured: list[tuple[str, list[str]]]) -> None:
    result = _invoke(
        [
            "enrich",
            "campaign",
            "--db",
            "db.sqlite",
            "--limit",
            "3",
            "--min-lines",
            "500",
            "--root-prefix",
            "C:/src",
            "--include-enriched",
            "--chunk-size",
            "5",
            "--max-projects",
            "20",
            "--tag-prefix",
            "camp",
            "--resume",
            "--execute",
            "--stop-on-error",
            "--output",
            "camp.json",
        ]
    )
    assert result.exit_code == 0
    script, argv = captured[0]
    assert script == "enrichment_campaign.py"
    for flag in ("--root-prefix", "--include-enriched", "--resume", "--execute", "--stop-on-error", "--output"):
        assert flag in argv


def test_index_audit_flags(captured: list[tuple[str, list[str]]]) -> None:
    result = _invoke(
        [
            "enrich",
            "index-audit",
            "--db",
            "db.sqlite",
            "--apply",
            "--json",
            "--output",
            "audit.json",
        ]
    )
    assert result.exit_code == 0
    script, argv = captured[0]
    assert script == "sqlite_index_audit.py"
    for flag in ("--apply", "--json", "--output"):
        assert flag in argv


def test_collectors_flags(captured: list[tuple[str, list[str]]]) -> None:
    result = _invoke(
        [
            "enrich",
            "collectors",
            "--db",
            "db.sqlite",
            "--source-path",
            "C:/src/proj",
            "--scan",
            "scan.jsonl",
            "--source-project",
            "proj",
            "--min-score",
            "5.5",
            "--top",
            "25",
            "--exclude-subpath",
            "vendor,dist",
            "--json",
            "--output",
            "col.json",
            "--dry-run",
            "--append",
        ]
    )
    assert result.exit_code == 0
    script, argv = captured[0]
    assert script == "file_collector_signals.py"
    for flag in ("--scan", "--source-project", "--exclude-subpath", "--json", "--output", "--dry-run", "--append"):
        assert flag in argv


def test_intelligence_flags(captured: list[tuple[str, list[str]]]) -> None:
    result = _invoke(
        [
            "enrich",
            "intelligence",
            "--db",
            "db.sqlite",
            "--source-path",
            "C:/src/proj",
            "--scan",
            "scan.jsonl",
            "--source-project",
            "proj",
            "--exclude-subpath",
            "node_modules",
            "--min-file-sim",
            "0.7",
            "--min-func-sim",
            "0.85",
            "--max-file-pairs",
            "500",
            "--max-func-pairs",
            "1000",
            "--complexity-threshold",
            "15",
            "--json",
            "--output",
            "intel.json",
            "--dry-run",
            "--append",
            "--no-default-excludes",
        ]
    )
    assert result.exit_code == 0
    script, argv = captured[0]
    assert script == "code_intelligence_signals.py"
    for flag in (
        "--scan",
        "--source-project",
        "--exclude-subpath",
        "--json",
        "--output",
        "--dry-run",
        "--append",
        "--no-default-excludes",
    ):
        assert flag in argv


def test_run_script_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """When the target script file is missing, _run_script raises BadParameter."""
    # Redirect _repo_root at an empty directory so "scripts/*.py" cannot exist.
    monkeypatch.setattr(enrich_mod, "_repo_root", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["enrich", "backlog", "--db", "db.sqlite"])
    assert result.exit_code != 0
    # BadParameter is surfaced by Typer as a usage error.
    assert "script not found" in (result.stdout + (result.stderr or ""))
