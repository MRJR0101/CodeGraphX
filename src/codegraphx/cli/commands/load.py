from __future__ import annotations

import typer

from codegraphx.cli.output import print_kv
from codegraphx.core.config import load_settings
from codegraphx.core.io import write_json
from codegraphx.core.search_index import build_search_index
from codegraphx.core.snapshots import create_snapshot
from codegraphx.core.stages import data_paths
from codegraphx.graph.neo4j_client import bootstrap_schema, check_connection, load_events_incremental


def command(
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    force_full: bool = typer.Option(False, "--force-full", help="Load all events and ignore incremental state"),
    snapshot_label: str = typer.Option("", "--snapshot-label", help="Optional label for created snapshot"),
    no_snapshot: bool = typer.Option(False, "--no-snapshot", help="Skip snapshot creation"),
) -> None:
    cfg = load_settings(settings)
    ok, msg = check_connection(cfg)
    if not ok:
        raise typer.BadParameter(f"Neo4j connection failed: {msg}")
    bootstrap_schema(cfg)
    paths = data_paths(cfg)
    result = load_events_incremental(
        cfg,
        events_path=str(paths.events),
        state_path=str(paths.load_state),
        force_full=force_full,
    )
    write_json(
        paths.load_meta,
        {
            "events_file": str(paths.events),
            "force_full": force_full,
            "total_input_events": result.total_input_events,
            "unique_events": result.unique_events,
            "loaded_events": result.loaded_events,
            "skipped_events": result.skipped_events,
            "loaded_nodes": result.loaded_nodes,
            "loaded_edges": result.loaded_edges,
        },
    )
    # Rebuild the FTS search index so `search` command is fast immediately.
    build_search_index(paths.events, paths.search_db)

    snapshot_path = ""
    if not no_snapshot:
        state = result.state_hashes
        snapshot = create_snapshot(
            cfg,
            hashes=state,
            meta={
                "force_full": force_full,
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

    print_kv(
        "load complete",
        {
            "events_file": paths.events,
            "loaded_events": result.loaded_events,
            "skipped_events": result.skipped_events,
            "loaded_nodes": result.loaded_nodes,
            "loaded_edges": result.loaded_edges,
            "force_full": force_full,
            "snapshot": snapshot_path or "disabled",
        },
    )
