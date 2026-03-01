from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "enrichment_backlog.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("enrichment_backlog_script", SCRIPT_PATH)
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
            path TEXT UNIQUE,
            file_count INTEGER,
            line_count INTEGER,
            has_readme INTEGER,
            has_tests INTEGER,
            has_git INTEGER,
            has_ci_cd INTEGER,
            has_docs INTEGER,
            has_license INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE codegraphx_enrichment (
            source_path TEXT UNIQUE
        )
        """
    )
    conn.commit()
    return conn


def test_query_backlog_filters_enriched(tmp_path: Path) -> None:
    mod = _load_script_module()
    conn = _init_db(tmp_path / "catalog.db")
    cur = conn.cursor()

    cur.executemany(
        """
        INSERT INTO projects
        (name, path, file_count, line_count, has_readme, has_tests, has_git, has_ci_cd, has_docs, has_license)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("A", r"c:\dev\projects\A", 10, 5000, 1, 1, 1, 0, 0, 0),
            ("B", r"c:\dev\projects\B", 30, 2000, 1, 0, 0, 0, 0, 0),
            ("C", r"c:\dev\projects\C", 5, 100, 0, 0, 0, 0, 0, 0),
        ],
    )
    cur.execute("INSERT INTO codegraphx_enrichment (source_path) VALUES (?)", (r"c:\dev\projects\A",))
    conn.commit()

    rows = mod.query_backlog(
        conn,
        limit=10,
        min_lines=200,
        root_prefix=r"c:\dev\projects",
        include_enriched=False,
    )
    paths = [r["path"] for r in rows]
    assert r"c:\dev\projects\A" not in paths
    assert r"c:\dev\projects\B" in paths
    assert r"c:\dev\projects\C" not in paths

    rows_with_enriched = mod.query_backlog(
        conn,
        limit=10,
        min_lines=200,
        root_prefix=r"c:\dev\projects",
        include_enriched=True,
    )
    paths_with_enriched = [r["path"] for r in rows_with_enriched]
    assert r"c:\dev\projects\A" in paths_with_enriched
    conn.close()


def test_render_text_for_empty_rows() -> None:
    mod = _load_script_module()
    assert mod._render_text([]) == "No candidates found."
