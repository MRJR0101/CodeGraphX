"""
Chunk large repository scans into multiple CodeGraphX `scan` runs and merge outputs.

This script is intended for very large roots (for example, PyToolbelt) where
single-shot scans are harder to monitor and recover.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    ".tox",
    ".eggs",
    "eggs",
    "site-packages",
    "99_Archive",
    "_analysis_reports",
    "_logs",
    "_planning",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run chunked CodeGraphX scans and optionally upsert scan summary into SQLite enrichment DB."
    )
    parser.add_argument("--target-root", required=True, help="Root directory to scan in chunks.")
    parser.add_argument(
        "--codegraphx-root",
        default="",
        help="CodeGraphX repository root. Default: inferred from this script location.",
    )
    parser.add_argument("--chunk-size", type=int, default=6, help="Top-level project directories per chunk.")
    parser.add_argument(
        "--tag",
        default="",
        help="Output tag. Default: normalized target root directory name.",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated additional top-level excludes under target root.",
    )
    parser.add_argument(
        "--max-projects",
        type=int,
        default=0,
        help="Optional cap on number of top-level directories to include (0 means no cap).",
    )
    parser.add_argument(
        "--update-db",
        default="",
        help="Optional SQLite DB path to upsert scan summary into codegraphx_enrichment.",
    )
    parser.add_argument(
        "--source-project",
        default="",
        help="Optional source project label for enrichment row. Default: tag value.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing chunk scan.jsonl files when present instead of rerunning those chunks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only generate chunk configs/settings and summary plan; do not run codegraphx scan.",
    )
    return parser.parse_args()


def _chunked(items: list[Path], size: int) -> Iterable[list[Path]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _sanitize_tag(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_").lower() or "scan"


def _run_scan(
    codegraphx_root: Path,
    projects_yaml: Path,
    settings_yaml: Path,
) -> tuple[int, str, str]:
    cmd = [
        "uv",
        "run",
        "codegraphx",
        "scan",
        "--config",
        str(projects_yaml),
        "--settings",
        str(settings_yaml),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(codegraphx_root),
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    return proc.returncode, stdout, stderr


def _line_count(path: Path) -> int:
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def _ensure_enrichment_table(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_enrichment (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL UNIQUE,
          source_project TEXT NOT NULL,
          scan_file_count INTEGER NOT NULL,
          parse_record_count INTEGER NOT NULL,
          event_count INTEGER NOT NULL,
          node_count INTEGER NOT NULL,
          edge_count INTEGER NOT NULL,
          project_nodes INTEGER NOT NULL,
          file_nodes INTEGER NOT NULL,
          function_nodes INTEGER NOT NULL,
          symbol_nodes INTEGER NOT NULL,
          module_nodes INTEGER NOT NULL,
          contains_edges INTEGER NOT NULL,
          defines_edges INTEGER NOT NULL,
          calls_edges INTEGER NOT NULL,
          imports_edges INTEGER NOT NULL,
          calls_function_edges INTEGER NOT NULL,
          scan_artifact TEXT NOT NULL,
          ast_artifact TEXT NOT NULL,
          events_artifact TEXT NOT NULL,
          settings_path TEXT NOT NULL,
          config_path TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    existing = {row[1] for row in cur.execute("PRAGMA table_info(codegraphx_enrichment)").fetchall()}
    extra = {
        "pipeline7_summary_artifact": "TEXT NOT NULL DEFAULT ''",
        "phase7_repo_fingerprint": "TEXT NOT NULL DEFAULT ''",
        "phase7_performance_json": "TEXT NOT NULL DEFAULT '{}'",
    }
    for col, ddl in extra.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE codegraphx_enrichment ADD COLUMN {col} {ddl}")


def _upsert_scan_summary(
    db_path: Path,
    source_path: str,
    source_project: str,
    scan_count: int,
    merged_scan: Path,
    summary_file: Path,
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        _ensure_enrichment_table(cur)
        cur.execute(
            """
            INSERT INTO codegraphx_enrichment (
              source_path, source_project,
              scan_file_count, parse_record_count, event_count,
              node_count, edge_count,
              project_nodes, file_nodes, function_nodes, symbol_nodes, module_nodes,
              contains_edges, defines_edges, calls_edges, imports_edges, calls_function_edges,
              scan_artifact, ast_artifact, events_artifact,
              settings_path, config_path,
              pipeline7_summary_artifact
            ) VALUES (
              ?, ?,
              ?, 0, 0,
              0, 0,
              0, 0, 0, 0, 0,
              0, 0, 0, 0, 0,
              ?, '', '',
              '', ?,
              ?
            )
            ON CONFLICT(source_path) DO UPDATE SET
              source_project=excluded.source_project,
              scan_file_count=excluded.scan_file_count,
              scan_artifact=excluded.scan_artifact,
              config_path=excluded.config_path,
              pipeline7_summary_artifact=excluded.pipeline7_summary_artifact,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                source_path,
                source_project,
                scan_count,
                str(merged_scan),
                str(summary_file),
                str(summary_file),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    args = _parse_args()
    target_root = Path(args.target_root).resolve()
    if not target_root.is_dir():
        raise SystemExit(f"Target root not found: {target_root}")

    codegraphx_root = Path(args.codegraphx_root).resolve() if args.codegraphx_root else Path(__file__).resolve().parents[1]
    if not (codegraphx_root / "config").is_dir():
        raise SystemExit(f"CodeGraphX root invalid (missing config directory): {codegraphx_root}")

    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be >= 1")

    tag = _sanitize_tag(args.tag or target_root.name)
    additional_excludes = {x.strip() for x in args.exclude.split(",") if x.strip()}
    excludes = set(DEFAULT_EXCLUDES) | additional_excludes

    top_dirs = sorted(
        [d for d in target_root.iterdir() if d.is_dir() and d.name not in excludes and not d.name.startswith(".")],
        key=lambda p: p.name.lower(),
    )
    if args.max_projects > 0:
        top_dirs = top_dirs[: args.max_projects]

    if not top_dirs:
        raise SystemExit(f"No eligible top-level directories found under {target_root}")

    cfg_dir = codegraphx_root / "config" / f"{tag}_chunks"
    chunk_data_root = codegraphx_root / "data" / f"{tag}_chunks"
    final_dir = codegraphx_root / "data" / f"{tag}_scan_complete"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    chunk_data_root.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    chunk_results: list[dict[str, object]] = []
    scan_files: list[Path] = []

    for idx, chunk in enumerate(_chunked(top_dirs, args.chunk_size), start=1):
        chunk_id = f"chunk_{idx:02d}"
        out_dir = chunk_data_root / chunk_id
        out_dir.mkdir(parents=True, exist_ok=True)

        projects_yaml = cfg_dir / f"projects_{chunk_id}.yaml"
        settings_yaml = cfg_dir / f"settings_{chunk_id}.yaml"

        lines = ["projects:"]
        chunk_excludes = sorted(DEFAULT_EXCLUDES | additional_excludes)

        for d in chunk:
            lines.append(f"  - name: {d.name}")
            lines.append(f"    root: {d.as_posix()}")
            lines.append("    exclude:")
            for ex in chunk_excludes:
                lines.append(f"      - {ex}")
        projects_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")

        settings_yaml.write_text(
            "\n".join(
                [
                    "run:",
                    f"  out_dir: {out_dir.as_posix()}",
                    "  max_files: 0",
                    '  include_ext: [".py", ".js", ".ts"]',
                    "",
                    "neo4j:",
                    "  uri: ${NEO4J_URI:-bolt://localhost:7687}",
                    "  user: ${NEO4J_USER:-neo4j}",
                    "  password: ${NEO4J_PASSWORD:-}",
                    "  database: neo4j",
                    "",
                    "memgraph:",
                    "  uri: ${MEMGRAPH_URI:-bolt://localhost:7687}",
                    "",
                    "meilisearch:",
                    "  host: ${MEILISEARCH_HOST:-localhost}",
                    "  port: ${MEILISEARCH_PORT:-7700}",
                    "  index: codegraphx",
                    "  enabled: false",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        scan_path = out_dir / "scan.jsonl"
        status = "planned"

        if args.dry_run:
            rows = _line_count(scan_path) if scan_path.exists() else 0
            if scan_path.exists():
                scan_files.append(scan_path)
            status = "planned_existing" if scan_path.exists() else "planned_new"
        elif args.resume and scan_path.exists():
            rows = _line_count(scan_path)
            scan_files.append(scan_path)
            status = "reused"
        else:
            rc, stdout, stderr = _run_scan(codegraphx_root, projects_yaml, settings_yaml)
            if rc != 0:
                raise SystemExit(
                    f"Scan failed for {chunk_id} with exit code {rc}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                )
            rows = _line_count(scan_path) if scan_path.exists() else 0
            if scan_path.exists():
                scan_files.append(scan_path)
            status = "scanned"

        chunk_results.append(
            {
                "chunk": chunk_id,
                "status": status,
                "projects": [d.name for d in chunk],
                "project_roots": [str(d) for d in chunk],
                "scan_file": str(scan_path),
                "rows": rows,
            }
        )

    merged_path = final_dir / f"scan_merged_{tag}.jsonl"
    summary_path = final_dir / f"scan_summary_{tag}.json"

    seen_paths: set[str] = set()
    merged_rows = 0
    with merged_path.open("w", encoding="utf-8") as out_f:
        for scan_file in scan_files:
            for raw_line in scan_file.read_text(encoding="utf-8").splitlines():
                if not raw_line.strip():
                    continue
                obj = json.loads(raw_line)
                file_path = str(obj.get("path", ""))
                if file_path in seen_paths:
                    continue
                seen_paths.add(file_path)
                out_f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                merged_rows += 1

    summary = {
        "root": str(target_root),
        "tag": tag,
        "chunk_size": args.chunk_size,
        "total_projects_scanned": len(top_dirs),
        "total_chunks": len(chunk_results),
        "chunk_results": chunk_results,
        "total_rows_raw": int(sum(int(c["rows"]) for c in chunk_results)),
        "total_rows_merged_unique": int(merged_rows),
        "merged_scan_file": str(merged_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if args.update_db and not args.dry_run:
        db_path = Path(args.update_db).resolve()
        source_project = args.source_project or tag
        _upsert_scan_summary(
            db_path=db_path,
            source_path=str(target_root),
            source_project=source_project,
            scan_count=merged_rows,
            merged_scan=merged_path,
            summary_file=summary_path,
        )

    print(
        json.dumps(
            {
                "status": "completed",
                "target_root": str(target_root),
                "chunks": len(chunk_results),
                "projects_scanned": len(top_dirs),
                "rows_raw": int(sum(int(c["rows"]) for c in chunk_results)),
                "rows_unique": int(merged_rows),
                "summary": str(summary_path),
                "merged": str(merged_path),
                "db_updated": bool(args.update_db and not args.dry_run),
                "dry_run": bool(args.dry_run),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
