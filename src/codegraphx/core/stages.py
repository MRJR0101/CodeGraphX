"""Core pipeline stages: scan, parse, extract.

Parser implementations live in codegraphx.core.parsers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from codegraphx.core.config import Project, RuntimeSettings
from codegraphx.core.io import read_json, read_jsonl, write_json, write_jsonl
from codegraphx.core.parsers import parse_js, parse_python


@dataclass(frozen=True)
class Paths:
    scan: Path
    ast: Path
    events: Path
    parse_cache: Path
    parse_meta: Path
    extract_cache: Path
    extract_meta: Path
    load_state: Path
    load_meta: Path
    search_db: Path


def data_paths(settings: RuntimeSettings) -> Paths:
    out = settings.out_dir
    return Paths(
        scan=out / "scan.jsonl",
        ast=out / "ast.jsonl",
        events=out / "events.jsonl",
        parse_cache=out / "parse.cache.json",
        parse_meta=out / "parse.meta.json",
        extract_cache=out / "extract.cache.json",
        extract_meta=out / "extract.meta.json",
        load_state=out / "load.state.json",
        load_meta=out / "load.meta.json",
        search_db=out / "search.db",
    )


def _iter_project_files(project: Project, settings: RuntimeSettings) -> Iterable[Path]:
    if not project.root.exists():
        return []
    exts = set(settings.include_ext)
    exclude_roots = {x.strip("/\\") for x in project.exclude if x.strip()}
    results: list[Path] = []
    for file_path in project.root.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(project.root)
        rel_parts = {part for part in rel.parts}
        if exclude_roots and rel_parts.intersection(exclude_roots):
            continue
        if file_path.suffix.lower() not in exts:
            continue
        results.append(file_path)
        if settings.max_files and len(results) >= settings.max_files:
            break
    return sorted(results)


def run_scan(projects: list[Project], settings: RuntimeSettings) -> tuple[Path, int]:
    paths = data_paths(settings)
    rows: list[dict[str, Any]] = []
    for project in projects:
        for path in _iter_project_files(project, settings):
            rel = path.relative_to(project.root).as_posix()
            rows.append({
                "project": project.name,
                "root": str(project.root),
                "path": str(path),
                "rel_path": rel,
                "ext": path.suffix.lower(),
                "size": path.stat().st_size,
            })
    write_jsonl(paths.scan, rows)
    return paths.scan, len(rows)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row_hash(row: dict[str, Any]) -> str:
    stable = {
        "project": row.get("project"),
        "path": row.get("path"),
        "rel_path": row.get("rel_path"),
        "language": row.get("language"),
        "line_count": row.get("line_count"),
        "functions": row.get("functions"),
        "imports": row.get("imports"),
        "calls": row.get("calls"),
        "function_calls": row.get("function_calls"),
    }
    return _content_hash(json.dumps(stable, sort_keys=True, ensure_ascii=False))


def run_parse(settings: RuntimeSettings) -> tuple[Path, int]:
    paths = data_paths(settings)
    scan_rows = read_jsonl(paths.scan)
    parse_cache_raw = read_json(paths.parse_cache)
    cached_files = parse_cache_raw.get("files", {})
    if not isinstance(cached_files, dict):
        cached_files = {}

    updated_cache: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    cache_hits = 0
    cache_misses = 0

    for row in scan_rows:
        path = Path(str(row["path"]))
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        file_hash = _content_hash(text)
        cached = cached_files.get(str(path), {})
        if isinstance(cached, dict) and cached.get("hash") == file_hash and isinstance(cached.get("row"), dict):
            parsed_row = cached["row"]
            rows.append(parsed_row)
            updated_cache[str(path)] = {"hash": file_hash, "row": parsed_row}
            cache_hits += 1
            continue

        ext = str(row.get("ext", "")).lower()
        if ext == ".py":
            funcs, imports, calls, function_calls, line_count = parse_python(text)
            language = "python"
        elif ext in {".js", ".ts"}:
            funcs, imports, calls, function_calls, line_count = parse_js(ext, text)
            language = "javascript"
        else:
            funcs, imports, calls, function_calls, line_count = [], [], [], [], len(text.splitlines())
            language = "unknown"

        parsed_row = {
            "project": row.get("project"),
            "path": row.get("path"),
            "rel_path": row.get("rel_path"),
            "language": language,
            "line_count": line_count,
            "functions": funcs,
            "imports": sorted(set(imports)),
            "calls": calls,
            "function_calls": function_calls,
        }
        rows.append(parsed_row)
        updated_cache[str(path)] = {"hash": file_hash, "row": parsed_row}
        cache_misses += 1

    write_jsonl(paths.ast, rows)
    write_json(paths.parse_cache, {"files": updated_cache})
    write_json(paths.parse_meta, {
        "files_total": len(rows),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    })
    return paths.ast, len(rows)


def run_extract(settings: RuntimeSettings, relations: bool = True) -> tuple[Path, int]:
    paths = data_paths(settings)
    ast_rows = read_jsonl(paths.ast)
    extract_cache_raw = read_json(paths.extract_cache)
    cached_files = extract_cache_raw.get("files", {})
    if not isinstance(cached_files, dict):
        cached_files = {}

    updated_cache: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    project_functions: dict[str, dict[str, list[str]]] = {}
    # Dir-scoped index: project -> rel_dir -> fn_name -> [uids]
    # Used for CALLS_FUNCTION resolution to avoid project-wide name collisions.
    project_dir_functions: dict[str, dict[str, dict[str, list[str]]]] = {}
    pending_fn_calls: list[tuple[str, str, list[str]]] = []
    cache_hits = 0
    cache_misses = 0

    for row in ast_rows:
        project = str(row.get("project", "unknown"))
        rel_path = str(row.get("rel_path", ""))
        file_uid = f"{project}:{rel_path}"

        # Collect function definitions and pending call edges for CALLS_FUNCTION resolution.
        funcs_raw = row.get("functions", [])
        if isinstance(funcs_raw, list):
            for fn in funcs_raw:
                if not isinstance(fn, dict):
                    continue
                fn_name = str(fn.get("name", "unknown"))
                fn_line = int(fn.get("line", 0) or 0)
                fn_uid = f"{file_uid}:{fn_name}:{fn_line}"
                project_map = project_functions.setdefault(project, {})
                project_map.setdefault(fn_name, []).append(fn_uid)
                # Also index by directory for scoped resolution.
                fn_dir = str(Path(rel_path).parent) if rel_path else ""
                dir_map = project_dir_functions.setdefault(project, {}).setdefault(fn_dir, {})
                dir_map.setdefault(fn_name, []).append(fn_uid)

        function_calls_raw = row.get("function_calls", [])
        if isinstance(function_calls_raw, list):
            for fn_call in function_calls_raw:
                if not isinstance(fn_call, dict):
                    continue
                fn_name = str(fn_call.get("name", ""))
                fn_line = int(fn_call.get("line", 0) or 0)
                src_uid = f"{file_uid}:{fn_name}:{fn_line}"
                called_names = fn_call.get("calls", [])
                if not isinstance(called_names, list):
                    continue
                pending_fn_calls.append((project, src_uid, [str(c) for c in called_names]))

        # Cache check and event generation.
        path_key = str(row.get("path", ""))
        row_hash = _row_hash(row)
        relation_mode = "relations-on" if relations else "relations-off"
        cache_key = f"{path_key}|{relation_mode}"
        cached = cached_files.get(cache_key, {})
        if isinstance(cached, dict) and cached.get("hash") == row_hash and isinstance(cached.get("events"), list):
            cached_events = [e for e in cached["events"] if isinstance(e, dict)]
            events.extend(cached_events)
            updated_cache[cache_key] = {"hash": row_hash, "events": cached_events}
            cache_hits += 1
            continue

        chunk: list[dict[str, Any]] = []
        chunk.append({"kind": "node", "label": "Project", "uid": project, "props": {"name": project}})
        chunk.append({
            "kind": "node", "label": "File", "uid": file_uid,
            "props": {
                "uid": file_uid, "project": project, "path": row.get("path"),
                "rel_path": rel_path, "language": row.get("language"),
                "line_count": row.get("line_count", 0),
            },
        })
        chunk.append({
            "kind": "edge", "type": "CONTAINS",
            "src_label": "Project", "src_uid": project,
            "dst_label": "File", "dst_uid": file_uid, "props": {},
        })

        funcs = row.get("functions", [])
        if isinstance(funcs, list):
            for fn in funcs:
                if not isinstance(fn, dict):
                    continue
                fn_name = str(fn.get("name", "unknown"))
                fn_line = int(fn.get("line", 0) or 0)
                fn_uid = f"{file_uid}:{fn_name}:{fn_line}"
                signature = f"{project}|{rel_path}|{fn_name}"
                chunk.append({
                    "kind": "node", "label": "Function", "uid": fn_uid,
                    "props": {
                        "uid": fn_uid, "name": fn_name, "line": fn_line,
                        "project": project, "file_uid": file_uid,
                        "signature_hash": _content_hash(signature),
                    },
                })
                chunk.append({
                    "kind": "edge", "type": "DEFINES",
                    "src_label": "File", "src_uid": file_uid,
                    "dst_label": "Function", "dst_uid": fn_uid, "props": {},
                })

        if relations:
            function_calls = row.get("function_calls", [])
            if isinstance(function_calls, list):
                for fn_call in function_calls:
                    if not isinstance(fn_call, dict):
                        continue
                    fn_name = str(fn_call.get("name", ""))
                    fn_line = int(fn_call.get("line", 0) or 0)
                    src_uid = f"{file_uid}:{fn_name}:{fn_line}"
                    for called in fn_call.get("calls", []):
                        target_name = str(called)
                        if not target_name:
                            continue
                        target_uid = f"symbol:{target_name}"
                        chunk.append({"kind": "node", "label": "Symbol", "uid": target_uid,
                                      "props": {"uid": target_uid, "name": target_name}})
                        chunk.append({"kind": "edge", "type": "CALLS",
                                      "src_label": "Function", "src_uid": src_uid,
                                      "dst_label": "Symbol", "dst_uid": target_uid, "props": {}})

            for imported in row.get("imports", []):
                imported_name = str(imported)
                imported_uid = f"module:{imported_name}"
                chunk.append({"kind": "node", "label": "Module", "uid": imported_uid,
                              "props": {"uid": imported_uid, "name": imported_name}})
                chunk.append({"kind": "edge", "type": "IMPORTS",
                              "src_label": "File", "src_uid": file_uid,
                              "dst_label": "Module", "dst_uid": imported_uid, "props": {}})

            for called in row.get("calls", []):
                target_name = str(called)
                target_uid = f"symbol:{target_name}"
                chunk.append({"kind": "node", "label": "Symbol", "uid": target_uid,
                              "props": {"uid": target_uid, "name": target_name}})
                chunk.append({"kind": "edge", "type": "CALLS",
                              "src_label": "File", "src_uid": file_uid,
                              "dst_label": "Symbol", "dst_uid": target_uid, "props": {}})

        events.extend(chunk)
        updated_cache[cache_key] = {"hash": row_hash, "events": chunk}
        cache_misses += 1

    call_function_edges: set[tuple[str, str]] = set()
    for project, src_uid, called_list in pending_fn_calls:
        # Resolve calls against same-directory functions only.
        # src_uid format: {project}:{rel_path}:{fn_name}:{fn_line}
        # Splitting on ":" gives [project, rel_path, fn_name, fn_line].
        uid_parts = src_uid.split(":")
        src_rel_path = uid_parts[1] if len(uid_parts) > 1 else ""
        src_dir = str(Path(src_rel_path).parent) if src_rel_path else ""
        dir_map = project_dir_functions.get(project, {}).get(src_dir, {})
        for called_name in called_list:
            for target_uid in dir_map.get(called_name, []):
                if src_uid == target_uid:
                    continue
                edge_key = (src_uid, target_uid)
                if edge_key in call_function_edges:
                    continue
                call_function_edges.add(edge_key)
                events.append({
                    "kind": "edge", "type": "CALLS_FUNCTION",
                    "src_label": "Function", "src_uid": src_uid,
                    "dst_label": "Function", "dst_uid": target_uid, "props": {},
                })

    write_jsonl(paths.events, events)
    write_json(paths.extract_cache, {"files": updated_cache})
    write_json(paths.extract_meta, {
        "rows_total": len(ast_rows),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "relations": relations,
        "events_total": len(events),
    })
    return paths.events, len(events)
