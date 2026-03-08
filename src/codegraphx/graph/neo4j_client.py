from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from neo4j import GraphDatabase

if TYPE_CHECKING:
    from neo4j import Driver

from codegraphx.core.config import RuntimeSettings
from codegraphx.core.io import read_json, read_jsonl, write_json
from codegraphx.core.snapshots import _event_identity


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class LoadResult:
    total_input_events: int
    unique_events: int
    loaded_events: int
    skipped_events: int
    loaded_nodes: int
    loaded_edges: int
    state_hashes: dict[str, str]


def _driver(settings: RuntimeSettings) -> Driver:
    if not settings.neo4j_password:
        raise ValueError(
            "Neo4j password is required. Set NEO4J_PASSWORD or neo4j.password in settings."
        )
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def bootstrap_schema(settings: RuntimeSettings) -> None:
    schema = [
        "CREATE CONSTRAINT project_name IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT file_id IF NOT EXISTS FOR (f:File) REQUIRE f.uid IS UNIQUE",
        "CREATE CONSTRAINT func_id IF NOT EXISTS FOR (fn:Function) REQUIRE fn.uid IS UNIQUE",
        "CREATE INDEX func_hash IF NOT EXISTS FOR (fn:Function) ON (fn.signature_hash)",
    ]
    with _driver(settings) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            for stmt in schema:
                session.run(stmt).consume()


def load_events(settings: RuntimeSettings, events_path: str) -> tuple[int, int]:
    rows = read_jsonl(Path(events_path))
    node_count = 0
    edge_count = 0
    with _driver(settings) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            for row in rows:
                kind = str(row.get("kind", ""))
                if kind == "node":
                    _merge_node(session, row)
                    node_count += 1
                elif kind == "edge":
                    _merge_edge(session, row)
                    edge_count += 1
    return node_count, edge_count


def _event_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# _event_identity is imported from codegraphx.core.snapshots (canonical definition)


def _prepare_incremental_batch(
    rows: list[dict[str, Any]],
    previous_hashes: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, str], int]:
    unique_rows: list[dict[str, Any]] = []
    new_hashes: dict[str, str] = {}
    seen_keys: set[str] = set()

    for idx, row in enumerate(rows):
        key = _event_identity(row, idx)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        current_hash = _event_hash(row)
        new_hashes[key] = current_hash
        if previous_hashes.get(key) == current_hash:
            continue
        unique_rows.append(row)

    skipped = len(seen_keys) - len(unique_rows)
    return unique_rows, new_hashes, skipped


def _event_record(row: dict[str, Any]) -> dict[str, str] | None:
    kind = str(row.get("kind", ""))
    if kind == "node":
        return {
            "kind": "node",
            "label": str(row.get("label", "")),
            "uid": str(row.get("uid", "")),
        }
    if kind == "edge":
        return {
            "kind": "edge",
            "type": str(row.get("type", "")),
            "src_label": str(row.get("src_label", "")),
            "src_uid": str(row.get("src_uid", "")),
            "dst_label": str(row.get("dst_label", "")),
            "dst_uid": str(row.get("dst_uid", "")),
        }
    return None


def _state_records(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    seen_keys: set[str] = set()
    for idx, row in enumerate(rows):
        key = _event_identity(row, idx)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        record = _event_record(row)
        if record is not None:
            records[key] = record
    return records


def _stale_state_records(
    previous_hashes: dict[str, str],
    previous_records: dict[str, Any],
    new_hashes: dict[str, str],
) -> list[dict[str, str]]:
    stale: list[dict[str, str]] = []
    for key in sorted(set(previous_hashes) - set(new_hashes)):
        record = previous_records.get(key)
        if isinstance(record, dict):
            stale.append({str(k): str(v) for k, v in record.items()})
    return stale


def _delete_stale_record(session: Any, record: dict[str, str]) -> None:
    kind = record.get("kind", "")
    if kind == "node":
        label = _safe_label(record.get("label", "Entity"))
        session.run(
            f"MATCH (n:{label} {{uid:$uid}}) DETACH DELETE n",
            uid=record.get("uid", ""),
        ).consume()
        return

    if kind == "edge":
        rel_type = _safe_label(record.get("type", "RELATED_TO"))
        src_label = _safe_label(record.get("src_label", "Entity"))
        dst_label = _safe_label(record.get("dst_label", "Entity"))
        session.run(
            (
                f"MATCH (a:{src_label} {{uid:$src_uid}})-[r:{rel_type}]->"
                f"(b:{dst_label} {{uid:$dst_uid}}) DELETE r"
            ),
            src_uid=record.get("src_uid", ""),
            dst_uid=record.get("dst_uid", ""),
        ).consume()


def load_events_incremental(
    settings: RuntimeSettings,
    events_path: str,
    state_path: str,
    force_full: bool = False,
) -> LoadResult:
    rows = read_jsonl(Path(events_path))
    state = read_json(Path(state_path))
    prev_hashes = state.get("hashes", {})
    if not isinstance(prev_hashes, dict):
        prev_hashes = {}
    prev_records = state.get("records", {})
    if not isinstance(prev_records, dict):
        prev_records = {}

    if force_full:
        unique_rows, new_hashes, _ = _prepare_incremental_batch(rows, {})
        skipped = 0
    else:
        unique_rows, new_hashes, skipped = _prepare_incremental_batch(rows, prev_hashes)

    new_records = _state_records(rows)
    stale_records = _stale_state_records(prev_hashes, prev_records, new_hashes)

    node_count = 0
    edge_count = 0
    with _driver(settings) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            for record in stale_records:
                _delete_stale_record(session, record)
            for row in unique_rows:
                kind = str(row.get("kind", ""))
                if kind == "node":
                    _merge_node(session, row)
                    node_count += 1
                elif kind == "edge":
                    _merge_edge(session, row)
                    edge_count += 1

    write_json(
        Path(state_path),
        {
            "hashes": new_hashes,
            "records": new_records,
            "total_input_events": len(rows),
            "unique_events": len(new_hashes),
            "loaded_events": len(unique_rows),
            "skipped_events": skipped,
        },
    )

    return LoadResult(
        total_input_events=len(rows),
        unique_events=len(new_hashes),
        loaded_events=len(unique_rows),
        skipped_events=skipped,
        loaded_nodes=node_count,
        loaded_edges=edge_count,
        state_hashes=new_hashes,
    )


def _merge_node(session: Any, row: dict[str, Any]) -> None:
    label = _safe_label(str(row.get("label", "Entity")))
    uid = str(row.get("uid", ""))
    props = row.get("props", {})
    if not isinstance(props, dict):
        props = {}
    q = f"MERGE (n:{label} {{uid:$uid}}) SET n += $props"
    session.run(q, uid=uid, props=props).consume()


def _merge_edge(session: Any, row: dict[str, Any]) -> None:
    # NOTE: MERGE on src/dst nodes here will create bare stub nodes (uid only, no props)
    # if an edge event arrives before its node events. The event stream from run_extract
    # always emits nodes before edges, so this is safe in normal operation. If you replay
    # a partial or reordered events file, orphan nodes with missing properties may appear.
    typ = _safe_label(str(row.get("type", "RELATED_TO")))
    src_label = _safe_label(str(row.get("src_label", "Entity")))
    dst_label = _safe_label(str(row.get("dst_label", "Entity")))
    src_uid = str(row.get("src_uid", ""))
    dst_uid = str(row.get("dst_uid", ""))
    props = row.get("props", {})
    if not isinstance(props, dict):
        props = {}
    q = (
        f"MERGE (a:{src_label} {{uid:$src_uid}}) "
        f"MERGE (b:{dst_label} {{uid:$dst_uid}}) "
        f"MERGE (a)-[r:{typ}]->(b) "
        "SET r += $props"
    )
    session.run(q, src_uid=src_uid, dst_uid=dst_uid, props=props).consume()


def _safe_label(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch == "_")
    return cleaned or "Entity"


def run_query(
    settings: RuntimeSettings,
    cypher: str,
    params: dict[str, Any] | None = None,
) -> QueryResult:
    with _driver(settings) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(cypher, parameters=params or {})
            data = result.data()
            columns = list(result.keys())
    return QueryResult(columns=columns, rows=data)


def check_connection(settings: RuntimeSettings) -> tuple[bool, str]:
    try:
        from neo4j.exceptions import Neo4jError
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)

    try:
        with _driver(settings) as driver:
            with driver.session(database=settings.neo4j_database) as session:
                session.run("RETURN 1 as ok").single()
        return True, "connected"
    except Neo4jError as exc:
        return False, f"neo4j error: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
