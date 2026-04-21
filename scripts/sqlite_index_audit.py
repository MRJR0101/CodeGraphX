"""
Audit and optionally apply recommended SQLite indexes for enrichment workflows.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

RECOMMENDED_INDEXES: List[Dict[str, Any]] = [
    {"table": "projects", "name": "idx_projects_path", "columns": ("path",)},
    {"table": "projects", "name": "idx_projects_line_count", "columns": ("line_count",)},
    {
        "table": "projects",
        "name": "idx_projects_line_count_path",
        "columns": ("line_count", "path"),
    },
    {
        "table": "codegraphx_enrichment",
        "name": "idx_enrichment_source_path",
        "columns": ("source_path",),
    },
    {
        "table": "codegraphx_enrichment",
        "name": "idx_enrichment_source_project",
        "columns": ("source_project",),
    },
    {
        "table": "codegraphx_enrichment",
        "name": "idx_enrichment_updated_at",
        "columns": ("updated_at",),
    },
    {
        "table": "codegraphx_file_signals",
        "name": "idx_file_signals_source_path",
        "columns": ("source_path",),
    },
    {
        "table": "codegraphx_file_signals",
        "name": "idx_file_signals_collector",
        "columns": ("is_file_collector",),
    },
    {
        "table": "codegraphx_file_signals",
        "name": "idx_file_signals_source_collector",
        "columns": ("source_path", "is_file_collector"),
    },
    {
        "table": "codegraphx_file_signals",
        "name": "idx_file_signals_score",
        "columns": ("collector_score",),
    },
    {
        "table": "codegraphx_project_signals",
        "name": "idx_project_signals_ratio",
        "columns": ("collector_ratio",),
    },
    {
        "table": "codegraphx_project_intelligence",
        "name": "idx_intel_source_project",
        "columns": ("source_project",),
    },
    {
        "table": "codegraphx_dependency_edges",
        "name": "idx_dep_source_internal",
        "columns": ("source_path", "is_internal"),
    },
    {
        "table": "codegraphx_call_edges",
        "name": "idx_call_source_internal",
        "columns": ("source_path", "is_internal"),
    },
    {
        "table": "codegraphx_call_edges",
        "name": "idx_call_caller",
        "columns": ("caller_uid",),
    },
    {
        "table": "codegraphx_complexity_nodes",
        "name": "idx_complexity_source_score",
        "columns": ("source_path", "cyclomatic"),
    },
    {
        "table": "codegraphx_similarity_pairs",
        "name": "idx_similarity_source_type",
        "columns": ("source_path", "pair_type"),
    },
    {
        "table": "codegraphx_similarity_pairs",
        "name": "idx_similarity_score",
        "columns": ("similarity",),
    },
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit SQLite indexes and optionally create recommended ones.")
    parser.add_argument("--db", required=True, help="Path to SQLite DB.")
    parser.add_argument("--apply", action="store_true", help="Create missing recommended indexes.")
    parser.add_argument("--json", action="store_true", help="Emit report as JSON.")
    parser.add_argument("--output", default="", help="Optional output path for the report.")
    return parser.parse_args()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _read_indexes(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    indexes: List[Dict[str, Any]] = []
    for row in conn.execute(f"PRAGMA index_list({table_name})").fetchall():
        name = str(row[1])
        is_unique = int(row[2]) == 1
        columns = tuple(
            str(col[2]) for col in conn.execute(f"PRAGMA index_info({name})").fetchall()
        )
        origin = str(row[3]) if len(row) >= 4 else ""
        partial = int(row[4]) == 1 if len(row) >= 5 else False
        indexes.append(
            {
                "name": name,
                "table": table_name,
                "columns": columns,
                "unique": is_unique,
                "origin": origin,
                "partial": partial,
            }
        )
    return indexes


def _has_equivalent_index(indexes: List[Dict[str, Any]], columns: Tuple[str, ...]) -> bool:
    for idx in indexes:
        idx_cols: Tuple[str, ...] = tuple(idx.get("columns", ()))
        if idx_cols[: len(columns)] == columns:
            return True
    return False


def build_index_report(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Analyze the database and report existing, missing, and skipped indexes."""
    table_indexes: Dict[str, List[Dict[str, Any]]] = {}
    table_columns: Dict[str, Set[str]] = {}

    for table in {str(r["table"]) for r in RECOMMENDED_INDEXES}:
        if not _table_exists(conn, table):
            table_indexes[table] = []
            table_columns[table] = set()
            continue
        table_indexes[table] = _read_indexes(conn, table)
        table_columns[table] = _table_columns(conn, table)

    missing: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for rec in RECOMMENDED_INDEXES:
        table = str(rec["table"])
        name = str(rec["name"])
        columns = tuple(str(c) for c in rec["columns"])

        if not _table_exists(conn, table):
            skipped.append(
                {"name": name, "table": table, "columns": columns, "reason": "table_missing"}
            )
            continue
        if not set(columns).issubset(table_columns[table]):
            skipped.append(
                {"name": name, "table": table, "columns": columns, "reason": "column_missing"}
            )
            continue
        if _has_equivalent_index(table_indexes[table], columns):
            continue
        missing.append({"name": name, "table": table, "columns": columns})

    return {
        "existing_indexes": table_indexes,
        "recommended_missing": missing,
        "recommended_skipped": skipped,
    }


def apply_missing_indexes(conn: sqlite3.Connection, missing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Execute CREATE INDEX statements for missing elements securely."""
    applied: List[Dict[str, Any]] = []
    cur = conn.cursor()
    for idx in missing:
        name = str(idx["name"])
        table = str(idx["table"])
        columns = tuple(str(c) for c in idx["columns"])
        col_sql = ", ".join(columns)
        cur.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({col_sql})")
        applied.append({"name": name, "table": table, "columns": columns})
    conn.commit()
    return applied


def _render_text(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    existing = report["existing_indexes"]
    missing = report["recommended_missing"]
    skipped = report["recommended_skipped"]

    lines.append("SQLite Index Audit")
    lines.append("==================")
    lines.append("")
    lines.append("Existing indexes:")
    for table, indexes in existing.items():
        lines.append(f"- {table}: {len(indexes)} index(es)")
        for idx in indexes:
            cols = ", ".join(idx["columns"])
            lines.append(
                f"  - {idx['name']} ({cols}) unique={idx['unique']} origin={idx['origin']}"
            )
    lines.append("")
    lines.append(f"Missing recommended indexes: {len(missing)}")
    for idx in missing:
        cols = ", ".join(idx["columns"])
        lines.append(f"- {idx['name']} ON {idx['table']} ({cols})")
    if skipped:
        lines.append("")
        lines.append(f"Skipped recommendations: {len(skipped)}")
        for idx in skipped:
            cols = ", ".join(idx["columns"])
            lines.append(f"- {idx['name']} ON {idx['table']} ({cols}) [{idx['reason']}]")
    if report.get("applied"):
        lines.append("")
        lines.append(f"Applied indexes: {len(report['applied'])}")
        for idx in report["applied"]:
            cols = ", ".join(idx["columns"])
            lines.append(f"- {idx['name']} ON {idx['table']} ({cols})")
    return "\n".join(lines)


def main() -> None:
    """Read arguments and route report builder/committer execution paths."""
    args = _parse_args()
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        report = build_index_report(conn)
        if args.apply:
            applied = apply_missing_indexes(conn, report["recommended_missing"])
            report["applied"] = applied
            report = build_index_report(conn) | {"applied": applied}
    finally:
        conn.close()

    output = json.dumps(report, indent=2) if args.json else _render_text(report)

    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
