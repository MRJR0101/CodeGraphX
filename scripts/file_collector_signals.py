"""
Detect file-collector scripts from CodeGraphX scan artifacts and persist signals in SQLite.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


SIGNAL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "walk": [
        re.compile(r"\bos\.walk\("),
        re.compile(r"\bos\.scandir\("),
        re.compile(r"\.rglob\("),
        re.compile(r"\.glob\("),
        re.compile(r"\.iterdir\("),
    ],
    "read": [
        re.compile(r"\bopen\("),
        re.compile(r"\bread_text\("),
        re.compile(r"\bread_bytes\("),
        re.compile(r"\bjson\.load\("),
        re.compile(r"\byaml\.safe_load\("),
        re.compile(r"\btomllib\.load\("),
        re.compile(r"\bcsv\.reader\("),
        re.compile(r"\bread_csv\("),
    ],
    "filter": [
        re.compile(r"\bsuffix\b"),
        re.compile(r"\bendswith\("),
        re.compile(r"\bfnmatch\b"),
        re.compile(r"\binclude\b"),
        re.compile(r"\bexclude\b"),
        re.compile(r"\bextension\b"),
        re.compile(r"\bpattern\b"),
    ],
    "metadata": [
        re.compile(r"\bstat\("),
        re.compile(r"\bst_size\b"),
        re.compile(r"\bmtime\b"),
        re.compile(r"\bhashlib\b"),
        re.compile(r"\bsha256\b"),
        re.compile(r"\bmd5\b"),
    ],
    "aggregate": [
        re.compile(r"\bwrite_text\("),
        re.compile(r"\bwrite_bytes\("),
        re.compile(r"\bjson\.dump\("),
        re.compile(r"\bcsv\.writer\("),
        re.compile(r"\breport\b", re.IGNORECASE),
        re.compile(r"\bmanifest\b", re.IGNORECASE),
        re.compile(r"\bcatalog\b", re.IGNORECASE),
        re.compile(r"\binventory\b", re.IGNORECASE),
        re.compile(r"\bindex\b", re.IGNORECASE),
    ],
    "fs_imports": [
        re.compile(r"^\s*import\s+os\b", re.MULTILINE),
        re.compile(r"^\s*from\s+pathlib\s+import\s+Path\b", re.MULTILINE),
        re.compile(r"^\s*import\s+glob\b", re.MULTILINE),
    ],
}

SIGNAL_WEIGHTS: dict[str, float] = {
    "walk": 2.0,
    "read": 2.0,
    "filter": 1.0,
    "metadata": 1.0,
    "aggregate": 1.0,
    "fs_imports": 0.5,
    "name_hint": 0.5,
}

NAME_HINT_RE = re.compile(r"(scan|scanner|index|catalog|inventory|audit|collect|discover|extract)", re.IGNORECASE)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect and persist file-collector script signals.")
    parser.add_argument("--db", required=True, help="Path to unified SQLite DB (project_catalog.db).")
    parser.add_argument(
        "--source-path",
        required=True,
        help="Project root path used as source_path key (for example: c:\\Dev\\PROJECTS\\00_PyToolbelt).",
    )
    parser.add_argument(
        "--scan",
        default="",
        help="Optional scan.jsonl path. Default: resolved from latest codegraphx_enrichment row for source_path.",
    )
    parser.add_argument(
        "--source-project",
        default="",
        help="Optional source_project label. Default: name from enrichment row or source-path directory name.",
    )
    parser.add_argument("--min-score", type=float, default=4.0, help="Minimum score threshold for collector classification.")
    parser.add_argument("--top", type=int, default=50, help="Top collector files to include in summary output.")
    parser.add_argument(
        "--exclude-subpath",
        default="",
        help="Comma-separated path substrings to skip (case-insensitive).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default="", help="Optional output path for report JSON/text.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze but do not write results into SQLite.")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append/update rows without replacing prior rows for source_path.",
    )
    return parser.parse_args()


def _normalize_path(value: str) -> str:
    return str(Path(value).resolve())


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


def _resolve_scan_artifact(
    conn: sqlite3.Connection,
    *,
    source_path: str,
    scan_override: str,
) -> tuple[Path, str]:
    if scan_override:
        scan = Path(scan_override).resolve()
        if not scan.exists():
            raise SystemExit(f"scan artifact not found: {scan}")
        return scan, ""

    if not _table_exists(conn, "codegraphx_enrichment"):
        raise SystemExit("codegraphx_enrichment table not found; pass --scan explicitly.")

    row = conn.execute(
        """
        SELECT scan_artifact, source_project
        FROM codegraphx_enrichment
        WHERE lower(source_path)=lower(?)
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (source_path,),
    ).fetchone()
    if row is None:
        raise SystemExit("no enrichment row for source_path and --scan not provided.")

    scan = Path(str(row[0] or "")).resolve()
    if not scan.exists():
        raise SystemExit(f"scan artifact from enrichment row not found: {scan}")
    return scan, str(row[1] or "")


def _language_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return "python"
    if ext in {".js", ".jsx"}:
        return "javascript"
    if ext in {".ts", ".tsx"}:
        return "typescript"
    return "unknown"


def score_file(path: Path, text: str, min_score: float) -> dict[str, Any]:
    active: dict[str, int] = {}
    evidence: list[str] = []
    score = 0.0

    for signal_name, patterns in SIGNAL_PATTERNS.items():
        matched = False
        for pat in patterns:
            if pat.search(text):
                matched = True
                break
        active[signal_name] = 1 if matched else 0
        if matched:
            score += SIGNAL_WEIGHTS.get(signal_name, 0.0)
            evidence.append(signal_name)

    if NAME_HINT_RE.search(path.name):
        active["name_hint"] = 1
        score += SIGNAL_WEIGHTS["name_hint"]
        evidence.append("name_hint")
    else:
        active["name_hint"] = 0

    is_collector = int(
        (active["walk"] and (active["read"] or active["metadata"] or active["aggregate"]) and score >= min_score)
        or score >= (min_score + 1.0)
    )

    return {
        "collector_score": round(score, 3),
        "is_file_collector": is_collector,
        "evidence": sorted(set(evidence)),
        "signals": active,
    }


def analyze_scan(
    scan_artifact: Path,
    min_score: float,
    *,
    exclude_subpaths: list[str],
) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    missing_files = 0
    skipped_by_filter = 0
    normalized_filters = [x.strip().lower().replace("\\", "/") for x in exclude_subpaths if x.strip()]

    for raw in scan_artifact.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        obj = json.loads(raw)
        file_path = Path(str(obj.get("path", "")))
        file_path_text = str(file_path).lower().replace("\\", "/")
        if normalized_filters and any(token in file_path_text for token in normalized_filters):
            skipped_by_filter += 1
            continue
        if not file_path.exists() or not file_path.is_file():
            missing_files += 1
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            missing_files += 1
            continue

        scored = score_file(file_path, text, min_score)
        rows.append(
            {
                "file_path": str(file_path.resolve()),
                "language": _language_for_path(file_path),
                "collector_score": float(scored["collector_score"]),
                "is_file_collector": int(scored["is_file_collector"]),
                "evidence": scored["evidence"],
                "signal_walk": int(scored["signals"]["walk"]),
                "signal_read": int(scored["signals"]["read"]),
                "signal_filter": int(scored["signals"]["filter"]),
                "signal_metadata": int(scored["signals"]["metadata"]),
                "signal_aggregate": int(scored["signals"]["aggregate"]),
                "signal_fs_imports": int(scored["signals"]["fs_imports"]),
                "signal_name_hint": int(scored["signals"]["name_hint"]),
            }
        )
    return rows, missing_files, skipped_by_filter


def _ensure_signal_tables(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_file_signals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL,
          source_project TEXT NOT NULL,
          file_path TEXT NOT NULL,
          language TEXT NOT NULL,
          collector_score REAL NOT NULL,
          is_file_collector INTEGER NOT NULL,
          signal_walk INTEGER NOT NULL,
          signal_read INTEGER NOT NULL,
          signal_filter INTEGER NOT NULL,
          signal_metadata INTEGER NOT NULL,
          signal_aggregate INTEGER NOT NULL,
          signal_fs_imports INTEGER NOT NULL,
          signal_name_hint INTEGER NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_path, file_path)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_project_signals (
          source_path TEXT PRIMARY KEY,
          source_project TEXT NOT NULL,
          files_analyzed INTEGER NOT NULL,
          collector_files INTEGER NOT NULL,
          collector_ratio REAL NOT NULL,
          min_score REAL NOT NULL,
          scan_artifact TEXT NOT NULL,
          top_collectors_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_file_signals_source_path ON codegraphx_file_signals (source_path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_file_signals_collector ON codegraphx_file_signals (is_file_collector)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_signals_source_collector ON codegraphx_file_signals (source_path, is_file_collector)"
    )


def persist_rows(
    conn: sqlite3.Connection,
    *,
    source_path: str,
    source_project: str,
    scan_artifact: Path,
    analyzed_rows: list[dict[str, Any]],
    min_score: float,
    top_n: int,
    replace_existing: bool,
) -> dict[str, Any]:
    cur = conn.cursor()
    _ensure_signal_tables(cur)
    if replace_existing:
        cur.execute("DELETE FROM codegraphx_file_signals WHERE source_path = ?", (source_path,))

    collector_rows = [r for r in analyzed_rows if int(r["is_file_collector"]) == 1]
    top_collectors = sorted(
        collector_rows,
        key=lambda r: (-float(r["collector_score"]), str(r["file_path"])),
    )[:top_n]

    for row in analyzed_rows:
        cur.execute(
            """
            INSERT INTO codegraphx_file_signals (
              source_path, source_project, file_path, language,
              collector_score, is_file_collector,
              signal_walk, signal_read, signal_filter, signal_metadata, signal_aggregate, signal_fs_imports, signal_name_hint,
              evidence_json
            ) VALUES (
              ?, ?, ?, ?,
              ?, ?,
              ?, ?, ?, ?, ?, ?, ?,
              ?
            )
            ON CONFLICT(source_path, file_path) DO UPDATE SET
              source_project=excluded.source_project,
              language=excluded.language,
              collector_score=excluded.collector_score,
              is_file_collector=excluded.is_file_collector,
              signal_walk=excluded.signal_walk,
              signal_read=excluded.signal_read,
              signal_filter=excluded.signal_filter,
              signal_metadata=excluded.signal_metadata,
              signal_aggregate=excluded.signal_aggregate,
              signal_fs_imports=excluded.signal_fs_imports,
              signal_name_hint=excluded.signal_name_hint,
              evidence_json=excluded.evidence_json,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                source_path,
                source_project,
                str(row["file_path"]),
                str(row["language"]),
                float(row["collector_score"]),
                int(row["is_file_collector"]),
                int(row["signal_walk"]),
                int(row["signal_read"]),
                int(row["signal_filter"]),
                int(row["signal_metadata"]),
                int(row["signal_aggregate"]),
                int(row["signal_fs_imports"]),
                int(row["signal_name_hint"]),
                json.dumps(row["evidence"], ensure_ascii=False),
            ),
        )

    files_analyzed = len(analyzed_rows)
    collector_count = len(collector_rows)
    ratio = round((collector_count / files_analyzed), 6) if files_analyzed else 0.0

    cur.execute(
        """
        INSERT INTO codegraphx_project_signals (
          source_path, source_project,
          files_analyzed, collector_files, collector_ratio, min_score,
          scan_artifact, top_collectors_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path) DO UPDATE SET
          source_project=excluded.source_project,
          files_analyzed=excluded.files_analyzed,
          collector_files=excluded.collector_files,
          collector_ratio=excluded.collector_ratio,
          min_score=excluded.min_score,
          scan_artifact=excluded.scan_artifact,
          top_collectors_json=excluded.top_collectors_json,
          updated_at=CURRENT_TIMESTAMP
        """,
        (
            source_path,
            source_project,
            files_analyzed,
            collector_count,
            ratio,
            float(min_score),
            str(scan_artifact),
            json.dumps(top_collectors, ensure_ascii=False),
        ),
    )
    conn.commit()

    return {
        "files_analyzed": files_analyzed,
        "collector_files": collector_count,
        "collector_ratio": ratio,
        "top_collectors": top_collectors,
    }


def _render_text(summary: dict[str, Any]) -> str:
    lines = [
        "File Collector Signals",
        "======================",
        f"source_project: {summary['source_project']}",
        f"source_path: {summary['source_path']}",
        f"scan_artifact: {summary['scan_artifact']}",
        f"files_analyzed: {summary['files_analyzed']}",
        f"collector_files: {summary['collector_files']}",
        f"collector_ratio: {summary['collector_ratio']}",
        f"missing_files: {summary['missing_files']}",
        "",
        "Top collectors:",
    ]
    for i, row in enumerate(summary["top_collectors"], start=1):
        lines.append(
            f"{i:>2}. score={row['collector_score']} | lang={row['language']} | {row['file_path']} "
            f"| evidence={','.join(row['evidence'])}"
        )
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    if args.min_score < 0:
        raise SystemExit("--min-score must be >= 0")
    if args.top < 1:
        raise SystemExit("--top must be >= 1")

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    source_path = _normalize_path(args.source_path)

    source_project = args.source_project or Path(source_path).name
    skipped_by_filter = 0
    conn = sqlite3.connect(str(db_path))
    try:
        scan_artifact, source_project_from_db = _resolve_scan_artifact(
            conn,
            source_path=source_path,
            scan_override=args.scan,
        )
        source_project = args.source_project or source_project_from_db or Path(source_path).name

        exclude_subpaths = [x.strip() for x in args.exclude_subpath.split(",") if x.strip()]
        analyzed_rows, missing_files, skipped_by_filter = analyze_scan(
            scan_artifact,
            args.min_score,
            exclude_subpaths=exclude_subpaths,
        )
        collector_rows = [r for r in analyzed_rows if int(r["is_file_collector"]) == 1]
        top_collectors = sorted(
            collector_rows,
            key=lambda r: (-float(r["collector_score"]), str(r["file_path"])),
        )[: args.top]

        persisted = {
            "files_analyzed": len(analyzed_rows),
            "collector_files": len(collector_rows),
            "collector_ratio": round((len(collector_rows) / len(analyzed_rows)), 6) if analyzed_rows else 0.0,
            "top_collectors": top_collectors,
        }
        if not args.dry_run:
            persisted = persist_rows(
                conn,
                source_path=source_path,
                source_project=source_project,
                scan_artifact=scan_artifact,
                analyzed_rows=analyzed_rows,
                min_score=float(args.min_score),
                top_n=args.top,
                replace_existing=not args.append,
            )
    finally:
        conn.close()

    summary = {
        "status": "completed",
        "source_path": source_path,
        "source_project": source_project,
        "scan_artifact": str(scan_artifact),
        "min_score": float(args.min_score),
        "files_analyzed": int(persisted["files_analyzed"]),
        "collector_files": int(persisted["collector_files"]),
        "collector_ratio": float(persisted["collector_ratio"]),
        "missing_files": int(missing_files),
        "skipped_by_filter": int(skipped_by_filter),
        "append_mode": bool(args.append),
        "db_updated": not args.dry_run,
        "top_collectors": persisted["top_collectors"],
    }

    output = json.dumps(summary, indent=2) if args.json else _render_text(summary)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
