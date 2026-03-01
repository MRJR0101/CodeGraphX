"""
Run backlog-driven enrichment campaigns against multiple projects.

By default this script runs in planning mode and only writes a campaign manifest.
Use --execute to run chunked_scan_enrich.py for each selected project.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or execute multi-project CodeGraphX enrichment campaign from SQLite backlog."
    )
    parser.add_argument("--db", required=True, help="Path to unified SQLite DB (project_catalog.db).")
    parser.add_argument(
        "--codegraphx-root",
        default="",
        help="CodeGraphX repository root. Default: inferred from this script location.",
    )
    parser.add_argument("--limit", type=int, default=5, help="How many ranked candidates to include.")
    parser.add_argument("--min-lines", type=int, default=500, help="Minimum project line count.")
    parser.add_argument(
        "--root-prefix",
        default="",
        help="Optional path prefix filter for candidate selection (for example: c:\\Dev\\PROJECTS).",
    )
    parser.add_argument(
        "--include-enriched",
        action="store_true",
        help="Include candidates already present in codegraphx_enrichment.",
    )
    parser.add_argument("--chunk-size", type=int, default=6, help="Chunk size passed to chunked_scan_enrich.py.")
    parser.add_argument(
        "--max-projects",
        type=int,
        default=0,
        help="Optional cap passed to chunked_scan_enrich.py (0 means no cap).",
    )
    parser.add_argument(
        "--tag-prefix",
        default="campaign",
        help="Prefix used when generating per-target scan tags.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Pass --resume to chunked_scan_enrich.py during execution.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run scans. Default behavior is plan-only mode (no scan execution).",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop campaign after first failed target execution.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional manifest output path. Default: data/enrichment_campaigns/campaign_<timestamp>.json",
    )
    return parser.parse_args()


def _sanitize_tag(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_").lower() or "scan"


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


def _query_candidates(
    conn: sqlite3.Connection,
    *,
    limit: int,
    min_lines: int,
    root_prefix: str,
    include_enriched: bool,
) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    has_enrichment = _table_exists(conn, "codegraphx_enrichment")

    if has_enrichment:
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
          AND COALESCE(p.path, '') <> ''
          AND (? = '' OR p.path LIKE ? || '%')
        """
        params: list[object] = [min_lines, root_prefix, root_prefix]
        if not include_enriched:
            sql += " AND e.source_path IS NULL"
    else:
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
          0 AS already_enriched,
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
        WHERE COALESCE(p.line_count, 0) >= ?
          AND COALESCE(p.path, '') <> ''
          AND (? = '' OR p.path LIKE ? || '%')
        """
        params = [min_lines, root_prefix, root_prefix]

    sql += " ORDER BY enrich_score DESC, line_count DESC LIMIT ?"
    params.append(limit)

    rows = [dict(r) for r in cur.execute(sql, params).fetchall()]
    for row in rows:
        row["enrich_score"] = round(float(row["enrich_score"]), 3)
    return rows


def _build_scan_command(
    *,
    chunk_script: Path,
    target_root: Path,
    chunk_size: int,
    tag: str,
    db_path: Path,
    source_project: str,
    max_projects: int,
    resume: bool,
    execute: bool,
) -> list[str]:
    cmd = [
        "uv",
        "run",
        "python",
        str(chunk_script),
        "--target-root",
        str(target_root),
        "--chunk-size",
        str(chunk_size),
        "--tag",
        tag,
        "--update-db",
        str(db_path),
        "--source-project",
        source_project,
    ]
    if max_projects > 0:
        cmd.extend(["--max-projects", str(max_projects)])
    if resume:
        cmd.append("--resume")
    if not execute:
        cmd.append("--dry-run")
    return cmd


def _tail_lines(text: str, max_lines: int = 20) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def main() -> None:
    args = _parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be >= 1")

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    codegraphx_root = Path(args.codegraphx_root).resolve() if args.codegraphx_root else Path(__file__).resolve().parents[1]
    chunk_script = codegraphx_root / "scripts" / "chunked_scan_enrich.py"
    if not chunk_script.exists():
        raise SystemExit(f"chunked_scan_enrich.py not found: {chunk_script}")

    data_dir = codegraphx_root / "data" / "enrichment_campaigns"
    data_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = Path(args.output).resolve() if args.output else (data_dir / f"campaign_{timestamp}.json")

    conn = sqlite3.connect(str(db_path))
    try:
        candidates = _query_candidates(
            conn,
            limit=args.limit,
            min_lines=args.min_lines,
            root_prefix=args.root_prefix,
            include_enriched=args.include_enriched,
        )
    finally:
        conn.close()

    runs: list[dict[str, object]] = []
    failed = False

    for idx, row in enumerate(candidates, start=1):
        source_name = str(row.get("name", f"project_{idx}"))
        source_path = Path(str(row.get("path", ""))).resolve()
        tag = _sanitize_tag(f"{args.tag_prefix}_{idx:02d}_{source_name}")
        cmd = _build_scan_command(
            chunk_script=chunk_script,
            target_root=source_path,
            chunk_size=args.chunk_size,
            tag=tag,
            db_path=db_path,
            source_project=source_name,
            max_projects=args.max_projects,
            resume=args.resume,
            execute=args.execute,
        )

        run: dict[str, object] = {
            "candidate_index": idx,
            "name": source_name,
            "path": str(source_path),
            "tag": tag,
            "enrich_score": row.get("enrich_score", 0.0),
            "already_enriched": int(row.get("already_enriched", 0)),
            "exists": source_path.exists() and source_path.is_dir(),
            "command": cmd,
        }

        if not run["exists"]:
            run["status"] = "skipped_missing_path"
            runs.append(run)
            continue

        if not args.execute:
            run["status"] = "planned"
            runs.append(run)
            continue

        started_at = datetime.now(UTC).isoformat()
        proc = subprocess.run(cmd, cwd=str(codegraphx_root), capture_output=True)
        ended_at = datetime.now(UTC).isoformat()

        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")

        run["started_at"] = started_at
        run["ended_at"] = ended_at
        run["return_code"] = proc.returncode
        run["stdout_tail"] = _tail_lines(stdout)
        run["stderr_tail"] = _tail_lines(stderr)
        run["status"] = "completed" if proc.returncode == 0 else "failed"

        runs.append(run)

        if proc.returncode != 0:
            failed = True
            if args.stop_on_error:
                break

    summary = {
        "campaign_id": f"campaign_{timestamp}",
        "created_at": datetime.now(UTC).isoformat(),
        "execute": bool(args.execute),
        "db_path": str(db_path),
        "codegraphx_root": str(codegraphx_root),
        "limit": int(args.limit),
        "min_lines": int(args.min_lines),
        "root_prefix": args.root_prefix,
        "include_enriched": bool(args.include_enriched),
        "chunk_size": int(args.chunk_size),
        "max_projects": int(args.max_projects),
        "tag_prefix": args.tag_prefix,
        "resume": bool(args.resume),
        "runs_total": len(runs),
        "runs_planned": sum(1 for r in runs if r.get("status") == "planned"),
        "runs_completed": sum(1 for r in runs if r.get("status") == "completed"),
        "runs_failed": sum(1 for r in runs if r.get("status") == "failed"),
        "runs_skipped_missing_path": sum(1 for r in runs if r.get("status") == "skipped_missing_path"),
        "failed": bool(failed),
        "manifest_path": str(manifest_path),
        "runs": runs,
    }
    manifest_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "completed",
                "execute": bool(args.execute),
                "failed": bool(failed),
                "runs_total": len(runs),
                "runs_completed": summary["runs_completed"],
                "runs_failed": summary["runs_failed"],
                "runs_planned": summary["runs_planned"],
                "runs_skipped_missing_path": summary["runs_skipped_missing_path"],
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
