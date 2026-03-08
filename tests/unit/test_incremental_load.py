from __future__ import annotations

from codegraphx.graph.neo4j_client import _prepare_incremental_batch, _stale_state_records


def test_prepare_incremental_batch_first_load_all_unique() -> None:
    rows = [
        {"kind": "node", "label": "Project", "uid": "A", "props": {"name": "A"}},
        {"kind": "node", "label": "File", "uid": "A:f.py", "props": {"uid": "A:f.py"}},
        {
            "kind": "edge",
            "type": "CONTAINS",
            "src_label": "Project",
            "src_uid": "A",
            "dst_label": "File",
            "dst_uid": "A:f.py",
            "props": {},
        },
    ]
    batch, hashes, skipped = _prepare_incremental_batch(rows, previous_hashes={})
    assert len(batch) == 3
    assert len(hashes) == 3
    assert skipped == 0


def test_prepare_incremental_batch_skips_unchanged_and_duplicate_identities() -> None:
    row_a = {"kind": "node", "label": "Project", "uid": "A", "props": {"name": "A"}}
    row_a_dup = {"kind": "node", "label": "Project", "uid": "A", "props": {"name": "A"}}
    row_b = {"kind": "node", "label": "File", "uid": "A:f.py", "props": {"uid": "A:f.py"}}
    first_batch, first_hashes, _ = _prepare_incremental_batch([row_a, row_b], previous_hashes={})
    assert len(first_batch) == 2

    second_batch, second_hashes, skipped = _prepare_incremental_batch(
        [row_a, row_a_dup, row_b],
        previous_hashes=first_hashes,
    )
    assert len(second_batch) == 0
    assert len(second_hashes) == 2
    assert skipped == 2


def test_prepare_incremental_batch_detects_changed_props() -> None:
    baseline = {"kind": "node", "label": "Project", "uid": "A", "props": {"name": "A"}}
    changed = {"kind": "node", "label": "Project", "uid": "A", "props": {"name": "A2"}}

    _, first_hashes, _ = _prepare_incremental_batch([baseline], previous_hashes={})
    second_batch, second_hashes, skipped = _prepare_incremental_batch([changed], previous_hashes=first_hashes)

    assert len(second_batch) == 1
    assert len(second_hashes) == 1
    assert skipped == 0


def test_stale_state_records_returns_removed_records() -> None:
    previous_hashes = {
        "node:Project:A": "h1",
        "node:File:A:f.py": "h2",
    }
    previous_records = {
        "node:Project:A": {"kind": "node", "label": "Project", "uid": "A"},
        "node:File:A:f.py": {"kind": "node", "label": "File", "uid": "A:f.py"},
    }
    new_hashes = {
        "node:Project:A": "h1",
    }

    stale = _stale_state_records(previous_hashes, previous_records, new_hashes)

    assert stale == [{"kind": "node", "label": "File", "uid": "A:f.py"}]
