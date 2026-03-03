"""
Scan and enrich top-level projects under a repository root into unified SQLite DB.

This is a repository-wide orchestration helper:
- discovers top-level project directories,
- runs `codegraphx scan` per project,
- upserts `codegraphx_enrichment`,
- runs collectors + intelligence enrichers.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_EXCLUDE_NAMES = [
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "site-packages",
    ".idea",
    ".vscode",
    "99_Archive",
    "90_GRAVEYARD",
    "AssessmentInbox",
    "incoming",
    "ms-playwright",
    ".gomodcache",
    "_analysis_reports",
    "_logs",
    "_planning",
    "archive",
]

DEFAULT_EXCLUDE_SUBPATH = (
    "assessmentinbox,devwide_rescan,incoming,99_archive,90_graveyard,.venv,node_modules,"
    "site-packages,ms-playwright,.gomodcache,archive,_analysis_reports,_logs,_planning,state\\backups"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repository-wide CodeGraphX enrichment campaign.")
    parser.add_argument("--root", required=True, help="Top-level repository root (for example: C:\\Repository).")
    parser.add_argument("--db", required=True, help="Unified SQLite DB path (project_catalog.db).")
    parser.add_argument(
        "--codegraphx-root",
        default="",
        help="CodeGraphX root. Default: inferred from this script location.",
    )
    parser.add_argument(
        "--campaign",
        default="",
        help="Campaign name. Default: repo_enrichment_<timestamp>.",
    )
    parser.add_argument(
        "--include",
        default="",
        help="Optional comma-separated top-level project names to include.",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Optional comma-separated top-level names to exclude in addition to defaults.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Optional scan max_files setting. 0 means unlimited.",
    )
    parser.add_argument(
        "--skip-if-enriched",
        action="store_true",
        help="Skip projects that already exist in codegraphx_enrichment by exact source_path.",
    )
    return parser.parse_args()


def _sanitize(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower() or "project"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - command is constructed from controlled internal inputs
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def _upsert_enrichment(
    conn: sqlite3.Connection,
    *,
    source_path: str,
    source_project: str,
    scan_file_count: int,
    scan_artifact: str,
    settings_path: str,
    config_path: str,
    summary_artifact: str,
) -> None:
    conn.execute(
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
          ?, ?,
          ?
        )
        ON CONFLICT(source_path) DO UPDATE SET
          source_project=excluded.source_project,
          scan_file_count=excluded.scan_file_count,
          scan_artifact=excluded.scan_artifact,
          settings_path=excluded.settings_path,
          config_path=excluded.config_path,
          pipeline7_summary_artifact=excluded.pipeline7_summary_artifact,
          updated_at=CURRENT_TIMESTAMP
        """,
        (
            source_path,
            source_project,
            int(scan_file_count),
            scan_artifact,
            settings_path,
            config_path,
            summary_artifact,
        ),
    )


def _discover_projects(
    root: Path,
    *,
    include: set[str],
    exclude: set[str],
) -> list[Path]:
    projects: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            continue
        if child.name in exclude:
            continue
        if include and child.name not in include:
            continue
        # Keep non-resolved root-relative paths so DB keys stay anchored to the
        # repository workspace even when junctions/symlinks are present.
        projects.append(child)
    return projects


def main() -> None:
    args = _parse_args()
    root = Path(args.root).resolve()
    db_path = Path(args.db).resolve()
    codegraphx_root = (
        Path(args.codegraphx_root).resolve() if args.codegraphx_root else Path(__file__).resolve().parents[1]
    )

    if not root.is_dir():
        raise SystemExit(f"root not found: {root}")
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")
    if not (codegraphx_root / "config").is_dir():
        raise SystemExit(f"invalid codegraphx root: {codegraphx_root}")

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    campaign = args.campaign or f"repo_enrichment_{timestamp}"
    cfg_dir = codegraphx_root / "config" / campaign
    out_root = codegraphx_root / "data" / campaign
    cfg_dir.mkdir(parents=True, exist_ok=True)
    out_root.mkdir(parents=True, exist_ok=True)

    include = {x.strip() for x in args.include.split(",") if x.strip()}
    exclude = {x.strip() for x in args.exclude.split(",") if x.strip()}
    projects = _discover_projects(root, include=include, exclude=exclude)

    conn = sqlite3.connect(str(db_path))
    existing = {row[0].lower() for row in conn.execute("SELECT source_path FROM codegraphx_enrichment")}

    rows: list[dict[str, object]] = []
    for proj in projects:
        source_path = str(proj)
        source_project = f"repo_{_sanitize(proj.name)}"
        label = _sanitize(proj.name)

        row: dict[str, object] = {
            "project_name": proj.name,
            "source_project": source_project,
            "source_path": source_path,
            "status": "planned",
        }

        if args.skip_if_enriched and source_path.lower() in existing:
            row["status"] = "skipped_already_enriched"
            rows.append(row)
            continue

        proj_cfg = cfg_dir / f"projects_{label}.yaml"
        set_cfg = cfg_dir / f"settings_{label}.yaml"
        out_dir = out_root / label
        out_dir.mkdir(parents=True, exist_ok=True)

        proj_lines = [
            "projects:",
            f"  - name: {source_project}",
            f"    root: {proj.as_posix()}",
            "    exclude:",
        ]
        for ex in DEFAULT_EXCLUDE_NAMES:
            proj_lines.append(f"      - {ex}")
        proj_cfg.write_text("\n".join(proj_lines) + "\n", encoding="utf-8")

        set_cfg.write_text(
            "\n".join(
                [
                    "run:",
                    f"  out_dir: {out_dir.as_posix()}",
                    f"  max_files: {int(args.max_files)}",
                    '  include_ext: [".py", ".js", ".ts"]',
                    "",
                    "neo4j:",
                    "  uri: ${NEO4J_URI:-bolt://localhost:7687}",
                    "  user: ${NEO4J_USER:-neo4j}",
                    "  password: ${NEO4J_PASSWORD:-}",
                    "  database: neo4j",
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

        scan_proc = _run(
            [
                "uv",
                "run",
                "codegraphx",
                "scan",
                "--config",
                str(proj_cfg),
                "--settings",
                str(set_cfg),
            ],
            codegraphx_root,
        )
        scan_file = out_dir / "scan.jsonl"
        scan_rows = _line_count(scan_file)

        row.update(
            {
                "scan_returncode": int(scan_proc.returncode),
                "scan_file": str(scan_file),
                "scan_file_count": int(scan_rows),
                "scan_stdout_tail": "\n".join((scan_proc.stdout or "").splitlines()[-20:]),
                "scan_stderr_tail": "\n".join((scan_proc.stderr or "").splitlines()[-20:]),
                "project_config": str(proj_cfg),
                "settings_config": str(set_cfg),
            }
        )

        if scan_proc.returncode != 0:
            row["status"] = "scan_failed"
            rows.append(row)
            continue

        summary_path = out_dir / "scan_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "source_path": source_path,
                    "source_project": source_project,
                    "scan_artifact": str(scan_file),
                    "scan_file_count": int(scan_rows),
                    "generated_at_utc": datetime.now(UTC).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        _upsert_enrichment(
            conn,
            source_path=source_path,
            source_project=source_project,
            scan_file_count=scan_rows,
            scan_artifact=str(scan_file),
            settings_path=str(set_cfg),
            config_path=str(proj_cfg),
            summary_artifact=str(summary_path),
        )
        conn.commit()

        if scan_rows <= 0:
            row["status"] = "scanned_no_files"
            rows.append(row)
            continue

        collectors = _run(
            [
                "uv",
                "run",
                "codegraphx",
                "enrich",
                "collectors",
                "--db",
                str(db_path),
                "--source-path",
                source_path,
                "--source-project",
                source_project,
                "--scan",
                str(scan_file),
                "--exclude-subpath",
                DEFAULT_EXCLUDE_SUBPATH,
                "--json",
            ],
            codegraphx_root,
        )
        intelligence = _run(
            [
                "uv",
                "run",
                "codegraphx",
                "enrich",
                "intelligence",
                "--db",
                str(db_path),
                "--source-path",
                source_path,
                "--source-project",
                source_project,
                "--scan",
                str(scan_file),
                "--exclude-subpath",
                DEFAULT_EXCLUDE_SUBPATH,
                "--json",
            ],
            codegraphx_root,
        )

        row.update(
            {
                "collectors_returncode": int(collectors.returncode),
                "intelligence_returncode": int(intelligence.returncode),
                "collectors_stdout_tail": "\n".join((collectors.stdout or "").splitlines()[-20:]),
                "collectors_stderr_tail": "\n".join((collectors.stderr or "").splitlines()[-20:]),
                "intelligence_stdout_tail": "\n".join((intelligence.stdout or "").splitlines()[-20:]),
                "intelligence_stderr_tail": "\n".join((intelligence.stderr or "").splitlines()[-20:]),
            }
        )

        if collectors.returncode == 0 and intelligence.returncode == 0:
            row["status"] = "enriched"
        else:
            row["status"] = "enrich_failed"
        rows.append(row)

    conn.close()

    report = {
        "campaign": campaign,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "root": str(root),
        "db": str(db_path),
        "total": len(rows),
        "enriched": sum(1 for r in rows if r.get("status") == "enriched"),
        "scanned_no_files": sum(1 for r in rows if r.get("status") == "scanned_no_files"),
        "skipped": sum(1 for r in rows if str(r.get("status", "")).startswith("skipped")),
        "failed": sum(1 for r in rows if str(r.get("status", "")).endswith("failed")),
        "items": rows,
    }
    report_path = out_root / f"{campaign}_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "campaign": campaign,
                "report": str(report_path),
                "total": report["total"],
                "enriched": report["enriched"],
                "scanned_no_files": report["scanned_no_files"],
                "skipped": report["skipped"],
                "failed": report["failed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
