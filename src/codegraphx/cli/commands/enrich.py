from __future__ import annotations

import subprocess
from pathlib import Path

import typer


app = typer.Typer(help="Enrichment automation commands")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _run_script(script_name: str, args: list[str]) -> None:
    root = _repo_root()
    script = root / "scripts" / script_name
    if not script.exists():
        raise typer.BadParameter(f"script not found: {script}")

    cmd = ["uv", "run", "python", str(script), *args]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True)
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")

    if stdout:
        typer.echo(stdout, nl=False)
    if stderr:
        typer.echo(stderr, err=True, nl=False)
    if proc.returncode != 0:
        raise typer.Exit(code=proc.returncode)


@app.command("backlog")
def backlog_cmd(
    db: str = typer.Option(..., "--db", help="Path to unified SQLite DB (project_catalog.db)."),
    limit: int = typer.Option(20, "--limit", help="Maximum candidates."),
    min_lines: int = typer.Option(1, "--min-lines", help="Minimum line_count filter."),
    root_prefix: str = typer.Option("", "--root-prefix", help="Optional candidate path prefix."),
    include_enriched: bool = typer.Option(False, "--include-enriched", help="Include already enriched candidates."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    output: str = typer.Option("", "--output", help="Optional output file path."),
) -> None:
    args = ["--db", db, "--limit", str(limit), "--min-lines", str(min_lines)]
    if root_prefix:
        args.extend(["--root-prefix", root_prefix])
    if include_enriched:
        args.append("--include-enriched")
    if json_output:
        args.append("--json")
    if output:
        args.extend(["--output", output])
    _run_script("enrichment_backlog.py", args)


@app.command("chunk-scan")
def chunk_scan_cmd(
    target_root: str = typer.Option(..., "--target-root", help="Root directory to chunk and scan."),
    chunk_size: int = typer.Option(6, "--chunk-size", help="Top-level directories per chunk."),
    tag: str = typer.Option("", "--tag", help="Output tag."),
    exclude: str = typer.Option("", "--exclude", help="Additional comma-separated excludes."),
    max_projects: int = typer.Option(0, "--max-projects", help="Optional project cap (0 means no cap)."),
    update_db: str = typer.Option("", "--update-db", help="Optional DB path for enrichment upsert."),
    source_project: str = typer.Option("", "--source-project", help="Optional enrichment source label."),
    resume: bool = typer.Option(False, "--resume", help="Reuse existing chunk outputs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; skip scan execution."),
) -> None:
    args = ["--target-root", target_root, "--chunk-size", str(chunk_size)]
    if tag:
        args.extend(["--tag", tag])
    if exclude:
        args.extend(["--exclude", exclude])
    if max_projects > 0:
        args.extend(["--max-projects", str(max_projects)])
    if update_db:
        args.extend(["--update-db", update_db])
    if source_project:
        args.extend(["--source-project", source_project])
    if resume:
        args.append("--resume")
    if dry_run:
        args.append("--dry-run")
    _run_script("chunked_scan_enrich.py", args)


@app.command("campaign")
def campaign_cmd(
    db: str = typer.Option(..., "--db", help="Path to unified SQLite DB."),
    limit: int = typer.Option(5, "--limit", help="Number of ranked candidates."),
    min_lines: int = typer.Option(500, "--min-lines", help="Minimum line_count filter."),
    root_prefix: str = typer.Option("", "--root-prefix", help="Optional candidate path prefix."),
    include_enriched: bool = typer.Option(False, "--include-enriched", help="Include already enriched candidates."),
    chunk_size: int = typer.Option(6, "--chunk-size", help="Chunk size for per-project scan."),
    max_projects: int = typer.Option(0, "--max-projects", help="Per-target project cap."),
    tag_prefix: str = typer.Option("campaign", "--tag-prefix", help="Per-target scan tag prefix."),
    resume: bool = typer.Option(False, "--resume", help="Reuse existing chunk output."),
    execute: bool = typer.Option(False, "--execute", help="Run scans; default is planning mode."),
    stop_on_error: bool = typer.Option(False, "--stop-on-error", help="Stop on first failed run."),
    output: str = typer.Option("", "--output", help="Optional campaign manifest path."),
) -> None:
    args = [
        "--db",
        db,
        "--limit",
        str(limit),
        "--min-lines",
        str(min_lines),
        "--chunk-size",
        str(chunk_size),
        "--max-projects",
        str(max_projects),
        "--tag-prefix",
        tag_prefix,
    ]
    if root_prefix:
        args.extend(["--root-prefix", root_prefix])
    if include_enriched:
        args.append("--include-enriched")
    if resume:
        args.append("--resume")
    if execute:
        args.append("--execute")
    if stop_on_error:
        args.append("--stop-on-error")
    if output:
        args.extend(["--output", output])
    _run_script("enrichment_campaign.py", args)


@app.command("index-audit")
def index_audit_cmd(
    db: str = typer.Option(..., "--db", help="Path to SQLite DB."),
    apply: bool = typer.Option(False, "--apply", help="Create missing recommended indexes."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON report."),
    output: str = typer.Option("", "--output", help="Optional report output path."),
) -> None:
    args = ["--db", db]
    if apply:
        args.append("--apply")
    if json_output:
        args.append("--json")
    if output:
        args.extend(["--output", output])
    _run_script("sqlite_index_audit.py", args)


@app.command("collectors")
def collectors_cmd(
    db: str = typer.Option(..., "--db", help="Path to unified SQLite DB."),
    source_path: str = typer.Option(..., "--source-path", help="Project root path key."),
    scan: str = typer.Option("", "--scan", help="Optional scan artifact override."),
    source_project: str = typer.Option("", "--source-project", help="Optional source project label."),
    min_score: float = typer.Option(4.0, "--min-score", help="Collector classification score threshold."),
    top: int = typer.Option(50, "--top", help="Top collector files in summary output."),
    exclude_subpath: str = typer.Option("", "--exclude-subpath", help="Comma-separated path substrings to skip."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    output: str = typer.Option("", "--output", help="Optional output path."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze but do not update DB."),
    append: bool = typer.Option(False, "--append", help="Append/update rows instead of replacing existing source rows."),
) -> None:
    args = [
        "--db",
        db,
        "--source-path",
        source_path,
        "--min-score",
        str(min_score),
        "--top",
        str(top),
    ]
    if scan:
        args.extend(["--scan", scan])
    if source_project:
        args.extend(["--source-project", source_project])
    if exclude_subpath:
        args.extend(["--exclude-subpath", exclude_subpath])
    if json_output:
        args.append("--json")
    if output:
        args.extend(["--output", output])
    if dry_run:
        args.append("--dry-run")
    if append:
        args.append("--append")
    _run_script("file_collector_signals.py", args)


@app.command("intelligence")
def intelligence_cmd(
    db: str = typer.Option(..., "--db", help="Path to unified SQLite DB."),
    source_path: str = typer.Option(..., "--source-path", help="Project root path key."),
    scan: str = typer.Option("", "--scan", help="Optional scan artifact override."),
    source_project: str = typer.Option("", "--source-project", help="Optional source project label."),
    exclude_subpath: str = typer.Option("", "--exclude-subpath", help="Comma-separated path substrings to skip."),
    min_file_sim: float = typer.Option(0.65, "--min-file-sim", help="Minimum file similarity threshold."),
    min_func_sim: float = typer.Option(0.8, "--min-func-sim", help="Minimum function similarity threshold."),
    max_file_pairs: int = typer.Option(1000, "--max-file-pairs", help="Maximum file similarity pairs."),
    max_func_pairs: int = typer.Option(2000, "--max-func-pairs", help="Maximum function similarity pairs."),
    complexity_threshold: int = typer.Option(10, "--complexity-threshold", help="High-complexity function threshold."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    output: str = typer.Option("", "--output", help="Optional output path."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze but do not update DB."),
    append: bool = typer.Option(False, "--append", help="Append/update rows instead of replacing existing source rows."),
    no_default_excludes: bool = typer.Option(
        False,
        "--no-default-excludes",
        help="Disable built-in excludes for virtualenvs/build/vendor mirrors.",
    ),
) -> None:
    args = [
        "--db",
        db,
        "--source-path",
        source_path,
        "--min-file-sim",
        str(min_file_sim),
        "--min-func-sim",
        str(min_func_sim),
        "--max-file-pairs",
        str(max_file_pairs),
        "--max-func-pairs",
        str(max_func_pairs),
        "--complexity-threshold",
        str(complexity_threshold),
    ]
    if scan:
        args.extend(["--scan", scan])
    if source_project:
        args.extend(["--source-project", source_project])
    if exclude_subpath:
        args.extend(["--exclude-subpath", exclude_subpath])
    if json_output:
        args.append("--json")
    if output:
        args.extend(["--output", output])
    if dry_run:
        args.append("--dry-run")
    if append:
        args.append("--append")
    if no_default_excludes:
        args.append("--no-default-excludes")
    _run_script("code_intelligence_signals.py", args)
