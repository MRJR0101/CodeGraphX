from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from codegraphx.cli.output import print_kv, print_rows
from codegraphx.core.config import load_settings
from codegraphx.core.io import write_json
from codegraphx.core.snapshots import diff_hash_maps, resolve_snapshot, snapshot_hashes


def _parse_identity(identity: str) -> dict[str, str]:
    parts = identity.split(":")
    if len(parts) < 2:
        return {"kind": "unknown", "type": "unknown", "identity": identity}
    if parts[0] == "node":
        label = parts[1]
        uid = ":".join(parts[2:]) if len(parts) > 2 else ""
        entry = {"kind": "node", "type": label, "uid": uid, "identity": identity}
        if label == "Function":
            uid_parts = uid.split(":")
            if len(uid_parts) >= 4:
                entry["project"] = uid_parts[0]
                entry["file"] = uid_parts[1]
                entry["function"] = uid_parts[2]
                entry["line"] = uid_parts[3]
        elif label == "File":
            uid_parts = uid.split(":")
            if len(uid_parts) >= 2:
                entry["project"] = uid_parts[0]
                entry["file"] = ":".join(uid_parts[1:])
        return entry

    if parts[0] == "edge":
        edge_type = parts[1]
        return {"kind": "edge", "type": edge_type, "identity": identity}

    return {"kind": "unknown", "type": parts[0], "identity": identity}


def _summarize_categories(diff: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for change in ("added", "removed", "changed"):
        values = diff.get(change, [])
        if not isinstance(values, list):
            continue
        bucket: dict[str, int] = {}
        for raw in values:
            parsed = _parse_identity(str(raw))
            key = f"{parsed.get('kind', 'unknown')}:{parsed.get('type', 'unknown')}"
            bucket[key] = bucket.get(key, 0) + 1
        for key, count in sorted(bucket.items()):
            rows.append({"change": change, "category": key, "count": count})
    return rows


def _changed_functions(diff: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for change in ("added", "removed", "changed"):
        values = diff.get(change, [])
        if not isinstance(values, list):
            continue
        for raw in values:
            parsed = _parse_identity(str(raw))
            if parsed.get("kind") == "node" and parsed.get("type") == "Function":
                rows.append(
                    {
                        "change": change,
                        "project": parsed.get("project", ""),
                        "file": parsed.get("file", ""),
                        "function": parsed.get("function", ""),
                        "line": parsed.get("line", ""),
                    }
                )
    return rows


def _changed_files(diff: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for change in ("added", "removed", "changed"):
        values = diff.get(change, [])
        if not isinstance(values, list):
            continue
        for raw in values:
            parsed = _parse_identity(str(raw))
            if parsed.get("kind") == "node" and parsed.get("type") == "File":
                rows.append(
                    {
                        "change": change,
                        "project": parsed.get("project", ""),
                        "file": parsed.get("file", ""),
                    }
                )
    return rows


def command(
    old: str = typer.Argument(..., help="Old snapshot id or path"),
    new: str = typer.Argument(..., help="New snapshot id or path"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    output: str = typer.Option("", "--output", "-o", help="Optional JSON output path"),
    show_lists: bool = typer.Option(False, "--show-lists", help="Show detailed changed files/functions"),
) -> None:
    cfg = load_settings(settings)
    old_path = resolve_snapshot(cfg, old)
    new_path = resolve_snapshot(cfg, new)
    diff = diff_hash_maps(snapshot_hashes(old_path), snapshot_hashes(new_path))
    counts = diff.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}

    category_rows = _summarize_categories(diff)
    function_rows = _changed_functions(diff)
    file_rows = _changed_files(diff)

    print_kv(
        "delta summary",
        {
            "old": old_path.stem,
            "new": new_path.stem,
            "added": counts.get("added", 0),
            "removed": counts.get("removed", 0),
            "changed": counts.get("changed", 0),
            "unchanged": counts.get("unchanged", 0),
            "changed_functions": len(function_rows),
            "changed_files": len(file_rows),
        },
    )
    print_rows("delta categories", category_rows, limit=max(20, len(category_rows)))
    if show_lists:
        print_rows("delta changed functions", function_rows, limit=max(20, len(function_rows)))
        print_rows("delta changed files", file_rows, limit=max(20, len(file_rows)))

    if output:
        payload = {
            "old": old_path.stem,
            "new": new_path.stem,
            "counts": counts,
            "categories": category_rows,
            "changed_functions": function_rows,
            "changed_files": file_rows,
        }
        write_json(Path(output), payload)

