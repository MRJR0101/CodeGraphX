from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from tree_sitter import Node

from codegraphx.core.config import Project, RuntimeSettings
from codegraphx.core.io import read_json, read_jsonl, write_json, write_jsonl

tslp: Any = None
try:
    import tree_sitter_language_pack as _tslp
    tslp = _tslp
except Exception:  # noqa: BLE001
    pass


PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+))")
JS_IMPORT_RE = re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]")
JS_REQUIRE_RE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")
JS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PY_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PY_TS_PARSER = tslp.get_parser("python") if tslp is not None else None
JS_TS_PARSER = tslp.get_parser("javascript") if tslp is not None else None
TS_TS_PARSER = tslp.get_parser("typescript") if tslp is not None else None


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
            rows.append(
                {
                    "project": project.name,
                    "root": str(project.root),
                    "path": str(path),
                    "rel_path": rel,
                    "ext": path.suffix.lower(),
                    "size": path.stat().st_size,
                }
            )
    write_jsonl(paths.scan, rows)
    return paths.scan, len(rows)


def _parse_python_with_treesitter(
    file_text: str,
) -> tuple[list[dict[str, Any]], list[str], list[str], list[dict[str, Any]], int]:
    src = file_text.encode("utf-8", errors="ignore")
    if PY_TS_PARSER is None:
        raise RuntimeError("tree-sitter python parser unavailable")

    tree = PY_TS_PARSER.parse(src)
    root = tree.root_node

    functions: list[dict[str, Any]] = []
    calls: list[str] = []
    function_calls: list[dict[str, Any]] = []

    def node_text(node: Node) -> str:
        return src[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def call_name_from_function_node(node: Node) -> str:
        text = node_text(node).strip()
        if "." in text:
            text = text.split(".")[-1]
        text = text.split("(")[0].strip()
        return text

    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in {"function_definition", "async_function_definition"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                fn_name = node_text(name_node)
                fn_line = int(node.start_point.row) + 1
                functions.append({"name": fn_name, "line": fn_line})

                fn_calls: list[str] = []
                inner_stack = [node]
                while inner_stack:
                    child = inner_stack.pop()
                    if child is not node and child.type in {"function_definition", "async_function_definition"}:
                        continue
                    if child.type == "call":
                        fn_node = child.child_by_field_name("function")
                        if fn_node is not None:
                            call_name = call_name_from_function_node(fn_node)
                            if call_name:
                                fn_calls.append(call_name)
                                calls.append(call_name)
                    inner_stack.extend(reversed(child.children))

                function_calls.append(
                    {
                        "name": fn_name,
                        "line": fn_line,
                        "calls": sorted(set(fn_calls)),
                    }
                )

        stack.extend(reversed(node.children))

    imports: list[str] = []
    for line in file_text.splitlines():
        m = PY_IMPORT_RE.match(line)
        if not m:
            continue
        module = (m.group(1) or m.group(2) or "").strip()
        if module:
            imports.append(module)

    line_count = len(file_text.splitlines())
    return (
        sorted(functions, key=lambda x: (int(x.get("line", 0)), str(x.get("name", "")))),
        sorted(set(imports)),
        calls,
        sorted(function_calls, key=lambda x: (int(x.get("line", 0)), str(x.get("name", "")))),
        line_count,
    )


def _parse_python(file_text: str) -> tuple[list[dict[str, Any]], list[str], list[str], list[dict[str, Any]], int]:
    if PY_TS_PARSER is not None:
        try:
            return _parse_python_with_treesitter(file_text)
        except Exception:  # noqa: BLE001
            pass

    try:
        tree = ast.parse(file_text)
    except SyntaxError:
        line_count = len(file_text.splitlines())
        return [], [], [], [], line_count

    functions: list[dict[str, Any]] = []
    imports: list[str] = []
    calls: list[str] = []
    function_calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": node.name, "line": node.lineno})
            fn_calls: list[str] = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Name):
                        fn_calls.append(fn.id)
                    elif isinstance(fn, ast.Attribute):
                        fn_calls.append(fn.attr)
            function_calls.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "calls": sorted(set(fn_calls)),
                }
            )
        elif isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                calls.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                calls.append(fn.attr)

    line_count = len(file_text.splitlines())
    return functions, imports, calls, function_calls, line_count


def _parse_js_like(file_text: str) -> tuple[list[dict[str, Any]], list[str], list[str], list[dict[str, Any]], int]:
    functions: list[dict[str, Any]] = []
    imports: list[str] = []
    calls: list[str] = []
    for lineno, line in enumerate(file_text.splitlines(), start=1):
        m_func = JS_FUNC_RE.search(line)
        if m_func:
            functions.append({"name": m_func.group(1), "line": lineno})
        m_import = JS_IMPORT_RE.search(line)
        if m_import:
            imports.append(m_import.group(1))
        for m_req in JS_REQUIRE_RE.finditer(line):
            imports.append(m_req.group(1))
        for call in PY_CALL_RE.findall(line):
            if call in {"if", "for", "while", "switch", "return"}:
                continue
            calls.append(call)
    line_count = len(file_text.splitlines())
    return functions, imports, calls, [], line_count


def _parse_js_ts_with_treesitter(
    file_text: str,
    parser: Any,
) -> tuple[list[dict[str, Any]], list[str], list[str], list[dict[str, Any]], int]:
    src = file_text.encode("utf-8", errors="ignore")
    tree = parser.parse(src)
    root = tree.root_node

    def node_text(node: Node) -> str:
        return src[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def call_name_from_node(node: Node) -> str:
        text = node_text(node).strip()
        if "." in text:
            text = text.split(".")[-1]
        text = text.split("(")[0].strip()
        return text

    functions: list[dict[str, Any]] = []
    imports: list[str] = []
    calls: list[str] = []
    function_calls: list[dict[str, Any]] = []

    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in {"function_declaration", "method_definition"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                fn_name = node_text(name_node)
                fn_line = int(node.start_point.row) + 1
                functions.append({"name": fn_name, "line": fn_line})

                fn_calls: list[str] = []
                inner_stack = [node]
                while inner_stack:
                    child = inner_stack.pop()
                    if child is not node and child.type in {"function_declaration", "method_definition"}:
                        continue
                    if child.type == "call_expression":
                        fn_node = child.child_by_field_name("function")
                        if fn_node is not None:
                            call_name = call_name_from_node(fn_node)
                            if call_name:
                                fn_calls.append(call_name)
                                calls.append(call_name)
                    inner_stack.extend(reversed(child.children))

                function_calls.append(
                    {
                        "name": fn_name,
                        "line": fn_line,
                        "calls": sorted(set(fn_calls)),
                    }
                )

        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node is not None:
                source_text = node_text(source_node).strip().strip("'\"")
                if source_text:
                    imports.append(source_text)

        if node.type == "call_expression":
            fn_node = node.child_by_field_name("function")
            if fn_node is not None:
                fn_name = call_name_from_node(fn_node)
                if fn_name == "require":
                    args_node = node.child_by_field_name("arguments")
                    if args_node is not None:
                        args_text = node_text(args_node)
                        m = JS_REQUIRE_RE.search(args_text)
                        if m:
                            imports.append(m.group(1))

        stack.extend(reversed(node.children))

    line_count = len(file_text.splitlines())
    return (
        sorted(functions, key=lambda x: (int(x.get("line", 0)), str(x.get("name", "")))),
        sorted(set(imports)),
        calls,
        sorted(function_calls, key=lambda x: (int(x.get("line", 0)), str(x.get("name", "")))),
        line_count,
    )


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
        file_hash = _sha1(text)
        cached = cached_files.get(str(path), {})
        if isinstance(cached, dict) and cached.get("hash") == file_hash and isinstance(cached.get("row"), dict):
            parsed_row = cached["row"]
            rows.append(parsed_row)
            updated_cache[str(path)] = {"hash": file_hash, "row": parsed_row}
            cache_hits += 1
            continue

        ext = str(row.get("ext", "")).lower()
        if ext == ".py":
            funcs, imports, calls, function_calls, line_count = _parse_python(text)
            language = "python"
        elif ext in {".js", ".ts"}:
            parser = JS_TS_PARSER if ext == ".js" else TS_TS_PARSER
            if parser is not None:
                try:
                    funcs, imports, calls, function_calls, line_count = _parse_js_ts_with_treesitter(text, parser)
                except Exception:  # noqa: BLE001
                    funcs, imports, calls, function_calls, line_count = _parse_js_like(text)
            else:
                funcs, imports, calls, function_calls, line_count = _parse_js_like(text)
            language = "javascript"
        else:
            funcs, imports, calls, function_calls, line_count = [], [], [], [], len(text.splitlines())
            language = "unknown"

        rows.append(
            {
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
        )
        updated_cache[str(path)] = {"hash": file_hash, "row": rows[-1]}
        cache_misses += 1

    write_jsonl(paths.ast, rows)
    write_json(paths.parse_cache, {"files": updated_cache})
    write_json(
        paths.parse_meta,
        {
            "files_total": len(rows),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
        },
    )
    return paths.ast, len(rows)


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


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
    return _sha1(json.dumps(stable, sort_keys=True, ensure_ascii=False))


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
    pending_fn_calls: list[tuple[str, str, list[str]]] = []
    for row in ast_rows:
        project = str(row.get("project", "unknown"))
        rel_path = str(row.get("rel_path", ""))
        file_uid = f"{project}:{rel_path}"
        funcs = row.get("functions", [])
        if isinstance(funcs, list):
            for fn in funcs:
                if not isinstance(fn, dict):
                    continue
                fn_name = str(fn.get("name", "unknown"))
                fn_line = int(fn.get("line", 0) or 0)
                fn_uid = f"{file_uid}:{fn_name}:{fn_line}"
                project_map = project_functions.setdefault(project, {})
                project_map.setdefault(fn_name, []).append(fn_uid)

        function_calls = row.get("function_calls", [])
        if isinstance(function_calls, list):
            for fn_call in function_calls:
                if not isinstance(fn_call, dict):
                    continue
                fn_name = str(fn_call.get("name", ""))
                fn_line = int(fn_call.get("line", 0) or 0)
                src_uid = f"{file_uid}:{fn_name}:{fn_line}"
                called_names = fn_call.get("calls", [])
                if not isinstance(called_names, list):
                    continue
                pending_fn_calls.append((project, src_uid, [str(c) for c in called_names]))
    cache_hits = 0
    cache_misses = 0
    for row in ast_rows:
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
        project = str(row.get("project", "unknown"))
        rel_path = str(row.get("rel_path", ""))
        file_uid = f"{project}:{rel_path}"
        chunk.append({"kind": "node", "label": "Project", "uid": project, "props": {"name": project}})
        chunk.append(
            {
                "kind": "node",
                "label": "File",
                "uid": file_uid,
                "props": {
                    "uid": file_uid,
                    "path": row.get("path"),
                    "rel_path": rel_path,
                    "language": row.get("language"),
                    "line_count": row.get("line_count", 0),
                },
            }
        )
        chunk.append(
            {
                "kind": "edge",
                "type": "CONTAINS",
                "src_label": "Project",
                "src_uid": project,
                "dst_label": "File",
                "dst_uid": file_uid,
                "props": {},
            }
        )

        funcs = row.get("functions", [])
        if isinstance(funcs, list):
            for fn in funcs:
                if not isinstance(fn, dict):
                    continue
                fn_name = str(fn.get("name", "unknown"))
                fn_line = int(fn.get("line", 0) or 0)
                fn_uid = f"{file_uid}:{fn_name}:{fn_line}"
                signature = f"{project}|{rel_path}|{fn_name}"
                chunk.append(
                    {
                        "kind": "node",
                        "label": "Function",
                        "uid": fn_uid,
                        "props": {
                            "uid": fn_uid,
                            "name": fn_name,
                            "line": fn_line,
                            "project": project,
                            "file_uid": file_uid,
                            "signature_hash": _sha1(signature),
                        },
                    }
                )
                chunk.append(
                    {
                        "kind": "edge",
                        "type": "DEFINES",
                        "src_label": "File",
                        "src_uid": file_uid,
                        "dst_label": "Function",
                        "dst_uid": fn_uid,
                        "props": {},
                    }
                )

        if relations:
            function_calls = row.get("function_calls", [])
            if isinstance(function_calls, list):
                for fn_call in function_calls:
                    if not isinstance(fn_call, dict):
                        continue
                    fn_name = str(fn_call.get("name", ""))
                    fn_line = int(fn_call.get("line", 0) or 0)
                    src_uid = f"{file_uid}:{fn_name}:{fn_line}"
                    called_names = fn_call.get("calls", [])
                    if not isinstance(called_names, list):
                        continue
                    for called in called_names:
                        target_name = str(called)
                        if not target_name:
                            continue
                        target_uid = f"symbol:{target_name}"
                        chunk.append(
                            {
                                "kind": "node",
                                "label": "Symbol",
                                "uid": target_uid,
                                "props": {"uid": target_uid, "name": target_name},
                            }
                        )
                        chunk.append(
                            {
                                "kind": "edge",
                                "type": "CALLS",
                                "src_label": "Function",
                                "src_uid": src_uid,
                                "dst_label": "Symbol",
                                "dst_uid": target_uid,
                                "props": {},
                            }
                        )

            imports = row.get("imports", [])
            if isinstance(imports, list):
                for imported in imports:
                    imported_name = str(imported)
                    imported_uid = f"module:{imported_name}"
                    chunk.append(
                        {
                            "kind": "node",
                            "label": "Module",
                            "uid": imported_uid,
                            "props": {"uid": imported_uid, "name": imported_name},
                        }
                    )
                    chunk.append(
                        {
                            "kind": "edge",
                            "type": "IMPORTS",
                            "src_label": "File",
                            "src_uid": file_uid,
                            "dst_label": "Module",
                            "dst_uid": imported_uid,
                            "props": {},
                        }
                    )

            calls = row.get("calls", [])
            if isinstance(calls, list):
                for called in calls:
                    target_name = str(called)
                    target_uid = f"symbol:{target_name}"
                    chunk.append(
                        {
                            "kind": "node",
                            "label": "Symbol",
                            "uid": target_uid,
                            "props": {"uid": target_uid, "name": target_name},
                        }
                    )
                    chunk.append(
                        {
                            "kind": "edge",
                            "type": "CALLS",
                            "src_label": "File",
                            "src_uid": file_uid,
                            "dst_label": "Symbol",
                            "dst_uid": target_uid,
                            "props": {},
                        }
                    )

        events.extend(chunk)
        updated_cache[cache_key] = {"hash": row_hash, "events": chunk}
        cache_misses += 1

    call_function_edges: set[tuple[str, str]] = set()
    for project, src_uid, called_list in pending_fn_calls:
        project_map = project_functions.get(project, {})
        for called_name in called_list:
            for target_uid in project_map.get(called_name, []):
                if src_uid == target_uid:
                    continue
                edge_key = (src_uid, target_uid)
                if edge_key in call_function_edges:
                    continue
                call_function_edges.add(edge_key)
                events.append(
                    {
                        "kind": "edge",
                        "type": "CALLS_FUNCTION",
                        "src_label": "Function",
                        "src_uid": src_uid,
                        "dst_label": "Function",
                        "dst_uid": target_uid,
                        "props": {},
                    }
                )

    write_jsonl(paths.events, events)
    write_json(paths.extract_cache, {"files": updated_cache})
    write_json(
        paths.extract_meta,
        {
            "rows_total": len(ast_rows),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "relations": relations,
            "events_total": len(events),
        },
    )
    return paths.events, len(events)
