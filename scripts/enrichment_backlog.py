"""
Rank project rows from ProjectCatalog SQLite for next CodeGraphX enrichment runs.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show ranked enrichment backlog from unified SQLite catalog.")
    parser.add_argument(
        "--db",
        required=True,
        help="Path to unified SQLite DB (project_catalog.db).",
    )
    parser.add_argument("--limit", type=int, default=20, help="Max candidates to return.")
    parser.add_argument("--min-lines", type=int, default=1, help="Minimum line_count for candidates.")
    parser.add_argument(
        "--root-prefix",
        default="",
        help="Optional path prefix filter (for example: c:\\Dev\\PROJECTS).",
    )
    parser.add_argument(
        "--include-enriched",
        action="store_true",
        help="Include already enriched projects in output.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output instead of plain text.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output file path (.json or .txt).",
    )
    return parser.parse_args()


def query_backlog(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    min_lines: int = 1,
    root_prefix: str = "",
    include_enriched: bool = False,
) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
    SELECT
      p.name,
      p.path,
      COALESCE(p.file_count, 0) AS file_count,
      COALESCE(p.line_count, 0) AS line_count,
      COALESCE(p.has_readme, 0) AS has_readme,
      COALESCE(p.has_tests, 0) AS has_tests,
      COALESCE(p.has_git, 0) AS has_git,
      COALESCE(p.has_ci_cd, 0) AS has_ci_cd,
      COALESCE(p.has_docs, 0) AS has_docs,
      COALESCE(p.has_license, 0) AS has_license,
      CASE WHEN e.source_path IS NULL THEN 0 ELSE 1 END AS already_enriched,
      (
        (COALESCE(p.line_count, 0) / 5000.0) +
        (COALESCE(p.file_count, 0) / 40.0) +
        (COALESCE(p.has_tests, 0) * 3.0) +
        (COALESCE(p.has_readme, 0) * 1.0) +
        (COALESCE(p.has_ci_cd, 0) * 1.5) +
        (COALESCE(p.has_docs, 0) * 1.0) +
        (COALESCE(p.has_license, 0) * 0.5) +
        (COALESCE(p.has_git, 0) * 1.0)
      ) AS enrich_score
    FROM projects p
    LEFT JOIN codegraphx_enrichment e
      ON e.source_path = p.path
    WHERE COALESCE(p.line_count, 0) >= ?
      AND (? = '' OR p.path LIKE ? || '%')
    """

    params: list[object] = [min_lines, root_prefix, root_prefix]
    if not include_enriched:
        sql += " AND e.source_path IS NULL"

    sql += " ORDER BY enrich_score DESC, line_count DESC LIMIT ?"
    params.append(limit)

    rows = [dict(r) for r in cur.execute(sql, params).fetchall()]
    for row in rows:
        row["enrich_score"] = round(float(row["enrich_score"]), 3)
    return rows


def _render_text(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No candidates found."

    lines = []
    for i, row in enumerate(rows, start=1):
        lines.append(
            f"{i:>2}. {row['name']} | score={row['enrich_score']} | "
            f"lines={row['line_count']} | files={row['file_count']} | "
            f"enriched={row['already_enriched']}"
        )
        lines.append(f"    {row['path']}")
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        rows = query_backlog(
            conn,
            limit=args.limit,
            min_lines=args.min_lines,
            root_prefix=args.root_prefix,
            include_enriched=args.include_enriched,
        )
    finally:
        conn.close()

    output = json.dumps(rows, indent=2) if args.json else _render_text(rows)

    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")

    print(output)


if __name__ == "__main__":
    main()
