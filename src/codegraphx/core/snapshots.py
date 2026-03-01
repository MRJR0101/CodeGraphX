from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codegraphx.core.config import RuntimeSettings
from codegraphx.core.io import read_json, read_jsonl, write_json


def snapshots_dir(settings: RuntimeSettings) -> Path:
    return settings.out_dir / "snapshots"


def _slugify(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in label.strip())
    return cleaned.strip("-_")


def create_snapshot(
    settings: RuntimeSettings,
    hashes: dict[str, str],
    meta: dict[str, Any] | None = None,
    label: str = "",
) -> Path:
    snap_dir = snapshots_dir(settings)
    snap_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = _slugify(label)
    name = f"{stamp}-{suffix}" if suffix else stamp
    path = snap_dir / f"{name}.json"
    payload = {
        "snapshot_id": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hashes": hashes,
        "meta": meta or {},
    }
    write_json(path, payload)
    return path


def list_snapshots(settings: RuntimeSettings) -> list[Path]:
    snap_dir = snapshots_dir(settings)
    if not snap_dir.exists():
        return []
    return sorted([p for p in snap_dir.glob("*.json") if p.is_file()])


def resolve_snapshot(settings: RuntimeSettings, token: str) -> Path:
    p = Path(token)
    if p.exists():
        return p
    snap_dir = snapshots_dir(settings)
    candidate = snap_dir / f"{token}.json"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Snapshot not found: {token}")


def snapshot_hashes(path: Path) -> dict[str, str]:
    raw = read_json(path)
    hashes = raw.get("hashes", {})
    if not isinstance(hashes, dict):
        return {}
    return {str(k): str(v) for k, v in hashes.items()}


def event_hashes(events_path: Path) -> dict[str, str]:
    rows = read_jsonl(events_path)
    hashes: dict[str, str] = {}
    seen_keys: set[str] = set()
    for index, row in enumerate(rows):
        key = _event_identity(row, index)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        payload = json.dumps(row, sort_keys=True, ensure_ascii=False)
        hashes[key] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return hashes


def diff_hash_maps(old: dict[str, str], new: dict[str, str]) -> dict[str, Any]:
    old_keys = set(old.keys())
    new_keys = set(new.keys())
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    shared = old_keys.intersection(new_keys)
    changed = sorted(k for k in shared if old.get(k) != new.get(k))
    unchanged = sorted(k for k in shared if old.get(k) == new.get(k))
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
            "old_total": len(old_keys),
            "new_total": len(new_keys),
        },
    }


def _event_identity(row: dict[str, Any], index: int) -> str:
    kind = str(row.get("kind", ""))
    if kind == "node":
        return f"node:{row.get('label', '')}:{row.get('uid', '')}"
    if kind == "edge":
        return (
            f"edge:{row.get('type', '')}:{row.get('src_label', '')}:{row.get('src_uid', '')}:"
            f"{row.get('dst_label', '')}:{row.get('dst_uid', '')}"
        )
    return f"unknown:{index}"
