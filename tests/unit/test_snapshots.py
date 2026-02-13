from __future__ import annotations

from pathlib import Path

from codegraphx.core.config import RuntimeSettings
from codegraphx.core.io import write_jsonl
from codegraphx.core.snapshots import create_snapshot, diff_hash_maps, event_hashes, list_snapshots, snapshot_hashes


def _settings(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        out_dir=tmp_path / "out",
        include_ext=[".py"],
        max_files=0,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="x",
        neo4j_database="neo4j",
        meilisearch_enabled=False,
        meilisearch_host="localhost",
        meilisearch_port=7700,
        meilisearch_index="codegraphx",
    )


def test_snapshot_create_and_list(tmp_path: Path) -> None:
    cfg = _settings(tmp_path)
    s1 = create_snapshot(cfg, hashes={"k1": "h1"}, meta={"m": 1}, label="first")
    s2 = create_snapshot(cfg, hashes={"k1": "h2", "k2": "h3"}, meta={"m": 2}, label="second")
    snaps = list_snapshots(cfg)
    assert s1 in snaps
    assert s2 in snaps
    assert snapshot_hashes(s1) == {"k1": "h1"}


def test_diff_hash_maps() -> None:
    old = {"a": "1", "b": "2", "c": "3"}
    new = {"b": "2", "c": "X", "d": "4"}
    diff = diff_hash_maps(old, new)
    counts = diff["counts"]
    assert counts == {
        "added": 1,
        "removed": 1,
        "changed": 1,
        "unchanged": 1,
        "old_total": 3,
        "new_total": 3,
    }
    assert diff["added"] == ["d"]
    assert diff["removed"] == ["a"]
    assert diff["changed"] == ["c"]
    assert diff["unchanged"] == ["b"]


def test_event_hashes_dedupes_by_identity(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    write_jsonl(
        events_path,
        [
            {"kind": "node", "label": "Project", "uid": "DemoA", "props": {"name": "DemoA"}},
            {"kind": "node", "label": "Project", "uid": "DemoA", "props": {"name": "DemoA-override"}},
            {
                "kind": "edge",
                "type": "CONTAINS",
                "src_label": "Project",
                "src_uid": "DemoA",
                "dst_label": "File",
                "dst_uid": "DemoA:a.py",
                "props": {},
            },
        ],
    )

    hashes = event_hashes(events_path)
    assert len(hashes) == 2
    assert "node:Project:DemoA" in hashes
    assert "edge:CONTAINS:Project:DemoA:File:DemoA:a.py" in hashes
