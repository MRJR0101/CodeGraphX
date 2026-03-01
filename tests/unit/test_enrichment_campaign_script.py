from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "enrichment_campaign.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("enrichment_campaign_script", SCRIPT_PATH)
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
    conn.commit()
    return conn


def test_build_scan_command_includes_flags(tmp_path: Path) -> None:
    mod = _load_script_module()
    chunk_script = tmp_path / "chunked_scan_enrich.py"
    chunk_script.write_text("print('x')\n", encoding="utf-8")

    cmd = mod._build_scan_command(
        chunk_script=chunk_script,
        target_root=Path(r"c:\dev\projects\alpha"),
        chunk_size=8,
        tag="campaign_alpha",
        db_path=Path(r"c:\repo\project_catalog.db"),
        source_project="alpha",
        max_projects=12,
        resume=True,
        execute=False,
    )
    rendered = " ".join(cmd)
    assert "--resume" in rendered
    assert "--dry-run" in rendered
    assert "--max-projects 12" in rendered
    assert "--chunk-size 8" in rendered
    assert "--tag campaign_alpha" in rendered


def test_query_candidates_without_enrichment_table(tmp_path: Path) -> None:
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
            ("alpha", r"c:\dev\projects\alpha", 20, 4000, 1, 1, 1, 1, 0, 1),
            ("beta", r"c:\dev\projects\beta", 5, 200, 1, 0, 0, 0, 0, 0),
        ],
    )
    conn.commit()

    rows = mod._query_candidates(
        conn,
        limit=10,
        min_lines=1000,
        root_prefix=r"c:\dev\projects",
        include_enriched=False,
    )
    assert len(rows) == 1
    assert rows[0]["name"] == "alpha"
    assert rows[0]["already_enriched"] == 0
    conn.close()
