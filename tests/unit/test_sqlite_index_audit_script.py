from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "sqlite_index_audit.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("sqlite_index_audit_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _init_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE projects (
            name TEXT,
            path TEXT,
            line_count INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE codegraphx_enrichment (
            source_path TEXT UNIQUE,
            source_project TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def test_build_index_report_detects_missing_recommendations(tmp_path: Path) -> None:
    mod = _load_script_module()
    conn = _init_db(tmp_path / "catalog.db")
    report = mod.build_index_report(conn)
    missing = {(r["table"], r["name"]) for r in report["recommended_missing"]}
    assert ("projects", "idx_projects_path") in missing
    assert ("projects", "idx_projects_line_count") in missing
    assert ("projects", "idx_projects_line_count_path") in missing
    assert ("codegraphx_enrichment", "idx_enrichment_source_project") in missing
    assert ("codegraphx_enrichment", "idx_enrichment_updated_at") in missing
    conn.close()


def test_apply_missing_indexes_reduces_missing_count(tmp_path: Path) -> None:
    mod = _load_script_module()
    conn = _init_db(tmp_path / "catalog.db")
    before = mod.build_index_report(conn)
    before_count = len(before["recommended_missing"])
    assert before_count > 0

    applied = mod.apply_missing_indexes(conn, before["recommended_missing"])
    assert len(applied) == before_count

    after = mod.build_index_report(conn)
    assert len(after["recommended_missing"]) == 0
    conn.close()
