from __future__ import annotations

from pathlib import Path

import typer

from codegraphx.cli.output import print_kv, print_rows
from codegraphx.core.config import load_settings
from codegraphx.core.io import read_json, write_json
from codegraphx.core.snapshots import (
    create_snapshot,
    diff_hash_maps,
    event_hashes,
    list_snapshots,
    resolve_snapshot,
    snapshot_hashes,
)
from codegraphx.core.stages import data_paths


app = typer.Typer(help="Snapshot commands")


@app.command("list")
def list_cmd(
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    snaps = list_snapshots(cfg)
    rows = [{"snapshot": p.stem, "path": str(p)} for p in snaps]
    print_rows("snapshots", rows, limit=max(20, len(rows)))


@app.command("create")
def create_cmd(
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    label: str = typer.Option("", "--label", help="Optional snapshot label"),
) -> None:
    cfg = load_settings(settings)
    paths = data_paths(cfg)
    state = read_json(paths.load_state)
    hashes = state.get("hashes", {})
    source = "load_state"
    meta = state
    if not isinstance(hashes, dict) or not hashes:
        if not paths.events.exists():
            raise typer.BadParameter(
                "no load state hashes found and events.jsonl is missing; run `codegraphx extract` or `codegraphx load` first"
            )
        hashes = event_hashes(paths.events)
        source = "events"
        meta = {"hash_source": "events", "events_path": str(paths.events), "events_hashed": len(hashes)}

    snapshot = create_snapshot(cfg, hashes={str(k): str(v) for k, v in hashes.items()}, meta=meta, label=label)
    print_kv("snapshot created", {"snapshot": snapshot.stem, "path": str(snapshot), "hash_source": source})


@app.command("diff")
def diff_cmd(
    old: str = typer.Argument(..., help="Old snapshot id or path"),
    new: str = typer.Argument(..., help="New snapshot id or path"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    show_keys: bool = typer.Option(False, "--show-keys", help="Show individual key lists"),
) -> None:
    cfg = load_settings(settings)
    old_path = resolve_snapshot(cfg, old)
    new_path = resolve_snapshot(cfg, new)
    diff = diff_hash_maps(snapshot_hashes(old_path), snapshot_hashes(new_path))
    counts = diff["counts"]
    if not isinstance(counts, dict):
        counts = {}
    print_kv(
        "snapshot diff",
        {
            "old": old_path.stem,
            "new": new_path.stem,
            "added": counts.get("added", 0),
            "removed": counts.get("removed", 0),
            "changed": counts.get("changed", 0),
            "unchanged": counts.get("unchanged", 0),
        },
    )
    if show_keys:
        for key in ("added", "removed", "changed"):
            values = diff.get(key, [])
            if not isinstance(values, list):
                continue
            rows = [{"identity": str(v)} for v in values]
            print_rows(f"snapshot diff: {key}", rows, limit=max(20, len(rows)))


def _identity_category(identity: str) -> str:
    parts = identity.split(":")
    if len(parts) < 2:
        return "unknown"
    if parts[0] == "node" and len(parts) >= 2:
        return f"node:{parts[1]}"
    if parts[0] == "edge" and len(parts) >= 2:
        return f"edge:{parts[1]}"
    return parts[0]


@app.command("report")
def report_cmd(
    old: str = typer.Argument(..., help="Old snapshot id or path"),
    new: str = typer.Argument(..., help="New snapshot id or path"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    output: str = typer.Option("", "--output", "-o", help="Optional JSON output path"),
) -> None:
    cfg = load_settings(settings)
    old_path = resolve_snapshot(cfg, old)
    new_path = resolve_snapshot(cfg, new)
    diff = diff_hash_maps(snapshot_hashes(old_path), snapshot_hashes(new_path))

    rows: list[dict[str, object]] = []
    for kind in ("added", "removed", "changed"):
        values = diff.get(kind, [])
        if not isinstance(values, list):
            continue
        bucket: dict[str, int] = {}
        for raw in values:
            cat = _identity_category(str(raw))
            bucket[cat] = bucket.get(cat, 0) + 1
        for cat, count in sorted(bucket.items()):
            rows.append({"change": kind, "category": cat, "count": count})

    counts = diff.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}

    print_kv(
        "snapshot report",
        {
            "old": old_path.stem,
            "new": new_path.stem,
            "added": counts.get("added", 0),
            "removed": counts.get("removed", 0),
            "changed": counts.get("changed", 0),
            "unchanged": counts.get("unchanged", 0),
        },
    )
    print_rows("snapshot report: categories", rows, limit=max(20, len(rows)))

    if output:
        payload = {
            "old": old_path.stem,
            "new": new_path.stem,
            "counts": counts,
            "categories": rows,
        }
        write_json(Path(output), payload)
