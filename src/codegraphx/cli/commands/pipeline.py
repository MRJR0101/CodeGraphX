"""Pipeline orchestration: run scan -> parse -> extract -> (optional) load.

Emits a machine-readable manifest describing each stage, its timings, output
paths, and record counts. The manifest is written to ``<out_dir>/pipeline_run_manifest.json``
so downstream tooling can inspect the run without parsing CLI output.
"""

from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any

import typer

from codegraphx.cli.output import print_kv, print_rows
from codegraphx.core.config import load_projects, load_settings
from codegraphx.core.io import write_json
from codegraphx.core.stages import data_paths, run_extract, run_parse, run_scan


app = typer.Typer(help="Pipeline orchestration commands")


def _stage_record(
    name: str,
    status: str,
    started: float,
    ended: float,
    output: str = "",
    count: int = 0,
    error: str = "",
) -> dict[str, Any]:
    return {
        "stage": name,
        "status": status,
        "started_at": started,
        "ended_at": ended,
        "duration_sec": round(ended - started, 4),
        "output": output,
        "count": count,
        "error": error,
    }


@app.command("run")
def run_cmd(
    config: str = typer.Option("config/projects.yaml", help="Projects config YAML"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    relations: bool = typer.Option(
        True, "--relations/--no-relations", help="Extract relation edges"
    ),
    skip_load: bool = typer.Option(
        True,
        "--skip-load/--with-load",
        help="Skip the Neo4j load stage (default). Use --with-load to "
        "include the load stage; this requires a reachable Neo4j instance.",
    ),
    force_full: bool = typer.Option(
        False, "--force-full", help="When loading, ignore incremental state"
    ),
    fresh: bool = typer.Option(
        False,
        "--fresh",
        help="When loading, use CREATE instead of MERGE (implies --force-full)",
    ),
    no_snapshot: bool = typer.Option(
        False, "--no-snapshot", help="When loading, skip snapshot creation"
    ),
    snapshot_label: str = typer.Option(
        "", "--snapshot-label", help="When loading, optional snapshot label"
    ),
    manifest: str = typer.Option(
        "",
        "--manifest",
        help="Optional explicit path for the run manifest JSON. "
        "Defaults to <out_dir>/pipeline_run_manifest.json.",
    ),
) -> None:
    """Run the full ingestion pipeline and emit a JSON run manifest."""

    cfg = load_settings(settings)
    projects = load_projects(config)
    paths = data_paths(cfg)

    manifest_path = Path(manifest) if manifest else (cfg.out_dir / "pipeline_run_manifest.json")

    stages: list[dict[str, Any]] = []
    overall_started = time.time()
    overall_status = "ok"
    first_error = ""

    def _finalize(extra: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {
            "version": 1,
            "projects_config": config,
            "settings": settings,
            "projects": [p.name for p in projects],
            "started_at": overall_started,
            "ended_at": time.time(),
            "status": overall_status,
            "error": first_error,
            "stages": stages,
            "manifest_path": str(manifest_path),
        }
        if extra:
            payload.update(extra)
        write_json(manifest_path, payload)

    # --- scan -----------------------------------------------------------------
    started = time.time()
    try:
        scan_out, scan_count = run_scan(projects, cfg)
        stages.append(
            _stage_record(
                "scan", "ok", started, time.time(), str(scan_out), scan_count
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        overall_status = "error"
        first_error = f"scan: {exc}"
        stages.append(
            _stage_record(
                "scan",
                "error",
                started,
                time.time(),
                error=f"{exc}\n{traceback.format_exc()}",
            )
        )
        _finalize()
        raise typer.Exit(code=1)

    # --- parse ----------------------------------------------------------------
    started = time.time()
    try:
        parse_out, parse_count = run_parse(cfg)
        stages.append(
            _stage_record(
                "parse", "ok", started, time.time(), str(parse_out), parse_count
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        overall_status = "error"
        first_error = f"parse: {exc}"
        stages.append(
            _stage_record(
                "parse",
                "error",
                started,
                time.time(),
                error=f"{exc}\n{traceback.format_exc()}",
            )
        )
        _finalize()
        raise typer.Exit(code=1)

    # --- extract --------------------------------------------------------------
    started = time.time()
    try:
        extract_out, extract_count = run_extract(cfg, relations=relations)
        stages.append(
            _stage_record(
                "extract",
                "ok",
                started,
                time.time(),
                str(extract_out),
                extract_count,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        overall_status = "error"
        first_error = f"extract: {exc}"
        stages.append(
            _stage_record(
                "extract",
                "error",
                started,
                time.time(),
                error=f"{exc}\n{traceback.format_exc()}",
            )
        )
        _finalize()
        raise typer.Exit(code=1)

    # --- load (optional) ------------------------------------------------------
    load_extra: dict[str, Any] = {}
    if skip_load:
        stages.append(
            _stage_record(
                "load",
                "skipped",
                time.time(),
                time.time(),
                output=str(paths.events),
                count=0,
            )
        )
    else:
        started = time.time()
        try:
            # Imported lazily so `pipeline run --skip-load` does not pull in
            # the Neo4j driver when it is not needed.
            from codegraphx.core.search_index import build_search_index
            from codegraphx.core.snapshots import create_snapshot
            from codegraphx.graph.neo4j_client import (
                bootstrap_schema,
                check_connection,
                load_events_incremental,
            )

            ok, msg = check_connection(cfg)
            if not ok:
                raise RuntimeError(f"Neo4j connection failed: {msg}")
            bootstrap_schema(cfg)
            if fresh:
                effective_force_full = True
            else:
                effective_force_full = force_full
            result = load_events_incremental(
                cfg,
                events_path=str(paths.events),
                state_path=str(paths.load_state),
                force_full=effective_force_full,
                fresh=fresh,
            )
            write_json(
                paths.load_meta,
                {
                    "events_file": str(paths.events),
                    "force_full": effective_force_full,
                    "fresh": fresh,
                    "total_input_events": result.total_input_events,
                    "unique_events": result.unique_events,
                    "loaded_events": result.loaded_events,
                    "skipped_events": result.skipped_events,
                    "loaded_nodes": result.loaded_nodes,
                    "loaded_edges": result.loaded_edges,
                },
            )
            build_search_index(paths.events, paths.search_db)

            snapshot_path = ""
            if not no_snapshot:
                snapshot = create_snapshot(
                    cfg,
                    hashes=result.state_hashes,
                    meta={
                        "force_full": effective_force_full,
                        "total_input_events": result.total_input_events,
                        "unique_events": result.unique_events,
                        "loaded_events": result.loaded_events,
                        "skipped_events": result.skipped_events,
                        "loaded_nodes": result.loaded_nodes,
                        "loaded_edges": result.loaded_edges,
                    },
                    label=snapshot_label,
                )
                snapshot_path = str(snapshot)

            load_extra = {
                "loaded_events": result.loaded_events,
                "skipped_events": result.skipped_events,
                "loaded_nodes": result.loaded_nodes,
                "loaded_edges": result.loaded_edges,
                "snapshot": snapshot_path,
            }
            stages.append(
                _stage_record(
                    "load",
                    "ok",
                    started,
                    time.time(),
                    output=str(paths.events),
                    count=result.loaded_events,
                )
            )
        except Exception as exc:
            overall_status = "error"
            first_error = f"load: {exc}"
            stages.append(
                _stage_record(
                    "load",
                    "error",
                    started,
                    time.time(),
                    error=f"{exc}\n{traceback.format_exc()}",
                )
            )
            _finalize({"load": load_extra})
            raise typer.Exit(code=1)

    _finalize({"load": load_extra} if load_extra else None)

    summary = {
        "projects": len(projects),
        "manifest": str(manifest_path),
        "status": overall_status,
    }
    print_kv("pipeline complete", summary)
    rows = [
        {
            "stage": s["stage"],
            "status": s["status"],
            "duration_sec": s["duration_sec"],
            "count": s["count"],
            "output": s["output"],
        }
        for s in stages
    ]
    print_rows("pipeline stages", rows, limit=max(10, len(rows)))
