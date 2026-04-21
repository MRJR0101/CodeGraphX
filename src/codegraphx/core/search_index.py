"""SQLite FTS5 search index for codegraphx.

Replaces the O(n) linear scan of events.jsonl in the search command.

Schema: one FTS5 virtual table (nodes_fts) with name and path as
full-text indexed columns. uid, label, project, rel_path are stored
as UNINDEXED columns for fast retrieval and Python-side filtering.

The index is built/rebuilt by build_search_index() which is called
by the load command after each successful load.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from codegraphx.core.io import read_jsonl


_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    name,
    path,
    uid UNINDEXED,
    label UNINDEXED,
    project UNINDEXED,
    rel_path UNINDEXED,
    tokenize = 'ascii'
);
"""

_META_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_QUERY_TERM_RE = re.compile(r"[A-Za-z0-9_]+")

def build_search_index(events_path: Path, db_path: Path) -> int:
    """Build (or rebuild) the SQLite FTS index from events.jsonl.

    Returns the number of node rows indexed.
    The existing index is dropped and recreated so the index always
    reflects the current events file exactly.
    """
    rows = read_jsonl(events_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        # Drop and recreate to ensure a clean rebuild.
        cur.execute("DROP TABLE IF EXISTS nodes_fts")
        cur.execute("DROP TABLE IF EXISTS search_meta")
        cur.executescript(_SCHEMA + _META_SCHEMA)

        insert_count = 0
        for row in rows:
            if row.get("kind") != "node":
                continue
            props = row.get("props", {})
            if not isinstance(props, dict):
                props = {}
            name = str(props.get("name", ""))
            path = str(props.get("path", ""))
            uid = str(row.get("uid", ""))
            label = str(row.get("label", ""))
            project = str(props.get("project", ""))
            rel_path = str(props.get("rel_path", ""))
            cur.execute(
                "INSERT INTO nodes_fts(name, path, uid, label, project, rel_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, path, uid, label, project, rel_path),
            )
            insert_count += 1

        cur.execute(
            "INSERT OR REPLACE INTO search_meta(key, value) VALUES ('events_path', ?)",
            (str(events_path),),
        )
        con.commit()
    finally:
        con.close()

    return insert_count



def query_search_index(
    db_path: "Path",
    query: str,
    index: str = "all",
    project: str = "",
    limit: int = 20,
) -> "list[dict[str, object]]":
    """Query the FTS index. Returns a list of matching node dicts.

    index: 'all' | 'functions' | 'symbols'
    project: if non-empty, filter to this project name only.
    Returns empty list if the index does not exist yet.
    """
    from pathlib import Path as _Path
    if not _Path(str(db_path)).exists():
        return []

    terms = _QUERY_TERM_RE.findall(query)
    if not terms:
        return []
    match_query = " AND ".join(f'"{term}"' for term in terms)

    label_filter = ""
    if index == "functions":
        label_filter = "AND label = 'Function'"
    elif index == "symbols":
        label_filter = "AND label IN ('Symbol', 'Module')"

    project_filter = ""
    params: list[object] = [match_query, limit]
    if project:
        project_filter = "AND project = ?"
        params = [match_query, project, limit]

    sql = (
        "SELECT name, path, uid, label, project, rel_path "
        "FROM nodes_fts "
        f"WHERE nodes_fts MATCH ? {label_filter} {project_filter} "
        "LIMIT ?"
    )

    import sqlite3
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        rows = []
        for name, fpath, uid, label, proj, rel_path in cur.fetchall():
            row: dict[str, object] = {"label": label, "uid": uid}
            if name:
                row["name"] = name
            if fpath:
                row["path"] = fpath
            if proj:
                row["project"] = proj
            if rel_path:
                row["rel_path"] = rel_path
            rows.append(row)
        return rows
    except sqlite3.OperationalError:
        # Table missing or corrupt -- caller gets empty result.
        return []
    finally:
        con.close()
