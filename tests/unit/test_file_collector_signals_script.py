from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "file_collector_signals.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("file_collector_signals_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyze_scan_detects_collector(tmp_path: Path) -> None:
    mod = _load_script_module()
    source_file = tmp_path / "scanner.py"
    source_file.write_text(
        "\n".join(
            [
                "import os",
                "from pathlib import Path",
                "def run(root):",
                "    out = []",
                "    for p, _, files in os.walk(root):",
                "        for f in files:",
                "            path = Path(p) / f",
                "            if path.suffix.endswith('.py'):",
                "                out.append(path.read_text(encoding='utf-8'))",
                "    return out",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    scan_artifact = tmp_path / "scan.jsonl"
    scan_artifact.write_text(
        json.dumps({"path": str(source_file), "ext": ".py"}) + "\n",
        encoding="utf-8",
    )

    rows, missing, skipped = mod.analyze_scan(scan_artifact, min_score=4.0, exclude_subpaths=[])
    assert missing == 0
    assert skipped == 0
    assert len(rows) == 1
    assert rows[0]["is_file_collector"] == 1
    assert rows[0]["signal_walk"] == 1
    assert rows[0]["signal_read"] == 1

    filtered_rows, filtered_missing, filtered_skipped = mod.analyze_scan(
        scan_artifact,
        min_score=4.0,
        exclude_subpaths=["scanner.py"],
    )
    assert filtered_missing == 0
    assert filtered_skipped == 1
    assert filtered_rows == []


def test_persist_rows_creates_and_updates_tables(tmp_path: Path) -> None:
    mod = _load_script_module()
    conn = sqlite3.connect(":memory:")
    analyzed_rows = [
        {
            "file_path": str(tmp_path / "a.py"),
            "language": "python",
            "collector_score": 5.0,
            "is_file_collector": 1,
            "evidence": ["walk", "read"],
            "signal_walk": 1,
            "signal_read": 1,
            "signal_filter": 0,
            "signal_metadata": 0,
            "signal_aggregate": 0,
            "signal_fs_imports": 1,
            "signal_name_hint": 1,
        },
        {
            "file_path": str(tmp_path / "b.py"),
            "language": "python",
            "collector_score": 1.0,
            "is_file_collector": 0,
            "evidence": [],
            "signal_walk": 0,
            "signal_read": 0,
            "signal_filter": 0,
            "signal_metadata": 0,
            "signal_aggregate": 0,
            "signal_fs_imports": 0,
            "signal_name_hint": 0,
        },
    ]

    summary = mod.persist_rows(
        conn,
        source_path=r"c:\dev\projects\alpha",
        source_project="alpha",
        scan_artifact=tmp_path / "scan.jsonl",
        analyzed_rows=analyzed_rows,
        min_score=4.0,
        top_n=10,
        replace_existing=True,
    )
    assert summary["files_analyzed"] == 2
    assert summary["collector_files"] == 1
    assert summary["collector_ratio"] == 0.5
    assert len(summary["top_collectors"]) == 1

    cur = conn.cursor()
    (file_rows,) = cur.execute("SELECT COUNT(*) FROM codegraphx_file_signals").fetchone()
    (project_rows,) = cur.execute("SELECT COUNT(*) FROM codegraphx_project_signals").fetchone()
    assert file_rows == 2
    assert project_rows == 1
    conn.close()
