"""
Compute reusable code intelligence signals from existing scan artifacts.

Signals persisted into SQLite:
- Dependency edges
- Call edges
- Function complexity
- File/function similarity pairs
- Project-level summary
"""

from __future__ import annotations

import argparse
import ast
import bisect
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, NamedTuple


SEEDS: tuple[int, ...] = (
    0x9E3779B1,
    0x85EBCA77,
    0xC2B2AE3D,
    0x27D4EB2F,
    0x165667B1,
    0xD3A2646C,
    0xB492B66F,
    0x9AE16A3B,
    0x7FEB352D,
    0x846CA68B,
    0xA2C2A,
    0x4CF5AD43,
)

JS_IMPORT_RE = re.compile(r"\bimport\s+.*?\bfrom\s+['\"]([^'\"]+)['\"]")
JS_REQUIRE_RE = re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)")
JS_FUNC_BLOCK_RE = re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{")
JS_ARROW_BLOCK_RE = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{"
)
JS_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
PY_LITERAL_RE = re.compile(r"(\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*')")
PY_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
PY_COMMENT_RE = re.compile(r"#.*")

JS_COMMENT_RE = re.compile(r"//.*?$|/\*[\s\S]*?\*/", re.MULTILINE)
JS_STRING_RE = re.compile(r"`[\s\S]*?`|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'")

JS_CALL_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "return",
    "catch",
    "function",
    "typeof",
    "console",
}

DEFAULT_EXCLUDE_SUBPATHS: tuple[str, ...] = (
    ".git/",
    "/.venv/",
    "/venv/",
    "/node_modules/",
    "/__pycache__/",
    "/.mypy_cache/",
    "/.pytest_cache/",
    "/site-packages/",
    "/dist/",
    "/build/",
    "/ms-playwright/",
    "/webkit.resources/",
)

class FunctionInfo(NamedTuple):
    uid: str
    file_path: str
    rel_path: str
    name: str
    start_line: int
    end_line: int
    language: str
    complexity: int
    calls: list[str]
    token_set: set[str]
    body_hash: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist code intelligence signals into unified SQLite DB.")
    parser.add_argument("--db", required=True, help="Path to unified SQLite DB (project_catalog.db).")
    parser.add_argument("--source-path", required=True, help="Project root path key.")
    parser.add_argument(
        "--scan",
        default="",
        help="Optional scan.jsonl override. Default: latest codegraphx_enrichment.scan_artifact for source-path.",
    )
    parser.add_argument("--source-project", default="", help="Optional source project label.")
    parser.add_argument(
        "--exclude-subpath",
        default="",
        help="Comma-separated path substrings to skip (case-insensitive).",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Disable built-in excludes for virtualenvs/build/vendor mirrors.",
    )
    parser.add_argument("--min-file-sim", type=float, default=0.65, help="Minimum file similarity (Jaccard).")
    parser.add_argument("--min-func-sim", type=float, default=0.8, help="Minimum function similarity (Jaccard).")
    parser.add_argument("--max-file-pairs", type=int, default=1000, help="Maximum file similarity pairs to store.")
    parser.add_argument("--max-func-pairs", type=int, default=2000, help="Maximum function similarity pairs to store.")
    parser.add_argument("--complexity-threshold", type=int, default=10, help="Threshold for high-complexity count.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default="", help="Optional output path.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without writing DB.")
    parser.add_argument("--append", action="store_true", help="Append/update rows without replacing existing source rows.")
    return parser.parse_args()


def _normalize_path(path: str) -> str:
    return str(Path(path).resolve())


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


def _resolve_scan_artifact(
    conn: sqlite3.Connection,
    *,
    source_path: str,
    scan_override: str,
) -> tuple[Path, str]:
    if scan_override:
        scan = Path(scan_override).resolve()
        if not scan.exists():
            raise SystemExit(f"scan artifact not found: {scan}")
        return scan, ""

    if not _table_exists(conn, "codegraphx_enrichment"):
        raise SystemExit("codegraphx_enrichment table missing; pass --scan.")

    row = conn.execute(
        """
        SELECT scan_artifact, source_project
        FROM codegraphx_enrichment
        WHERE lower(source_path)=lower(?)
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (source_path,),
    ).fetchone()
    if row is None:
        raise SystemExit("no codegraphx_enrichment row for source-path and --scan not provided.")

    scan = Path(str(row[0] or "")).resolve()
    if not scan.exists():
        raise SystemExit(f"scan artifact from enrichment row not found: {scan}")
    return scan, str(row[1] or "")


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize_python_body(text: str) -> str:
    text = PY_COMMENT_RE.sub("", text)
    text = PY_LITERAL_RE.sub("STR", text)
    text = PY_NUMBER_RE.sub("NUM", text)
    text = re.sub(r"\s+", "", text)
    return text


def _normalize_js_body(text: str) -> str:
    text = JS_COMMENT_RE.sub("", text)
    text = JS_STRING_RE.sub("STR", text)
    text = PY_NUMBER_RE.sub("NUM", text)
    text = re.sub(r"\s+", "", text)
    return text


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()


def _hash_token(token: str, seed: int) -> int:
    digest = hashlib.sha1(f"{seed}:{token}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _minhash_signature(tokens: set[str]) -> tuple[int, ...]:
    if not tokens:
        return tuple(0 for _ in SEEDS)
    values: list[int] = []
    for seed in SEEDS:
        values.append(min(_hash_token(token, seed) for token in tokens))
    return tuple(values)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def _signature_candidates(signatures: dict[str, tuple[int, ...]], band_size: int = 3) -> set[tuple[str, str]]:
    if band_size < 1:
        band_size = 1
    pair_set: set[tuple[str, str]] = set()
    if not signatures:
        return pair_set

    sig_len = len(next(iter(signatures.values())))
    for start in range(0, sig_len, band_size):
        buckets: dict[tuple[int, ...], list[str]] = defaultdict(list)
        for item_id, sig in signatures.items():
            key = sig[start : start + band_size]
            buckets[key].append(item_id)
        for members in buckets.values():
            if len(members) < 2:
                continue
            if len(members) > 200:
                continue
            members.sort()
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    pair_set.add((members[i], members[j]))
    return pair_set


def _module_from_rel_path(rel_path: str) -> str:
    path = Path(rel_path)
    if path.suffix.lower() != ".py":
        return ""
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _python_call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _python_cyclomatic(node: ast.AST) -> int:
    branch_nodes: tuple[type[Any], ...] = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.ExceptHandler,
        ast.IfExp,
        ast.With,
        ast.AsyncWith,
        ast.BoolOp,
        ast.comprehension,
        ast.Match,
        ast.match_case,
    )
    complexity = 1
    for sub in ast.walk(node):
        if isinstance(sub, branch_nodes):
            complexity += 1
    return complexity


def _python_function_source(text: str, node: ast.AST) -> str:
    if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
        return ""
    lines = text.splitlines()
    start = max(int(getattr(node, "lineno", 1)) - 1, 0)
    end = max(int(getattr(node, "end_lineno", start + 1)), start + 1)
    return "\n".join(lines[start:end])


def _parse_python_file(
    *,
    file_path: str,
    rel_path: str,
    text: str,
) -> tuple[list[str], list[FunctionInfo], set[str]]:
    imports: list[str] = []
    functions: list[FunctionInfo] = []
    file_tokens: set[str] = set()

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return imports, functions, file_tokens

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                file_tokens.update(TOKEN_RE.findall(alias.name.lower()))
        elif isinstance(node, ast.ImportFrom):
            level = int(node.level or 0)
            module = node.module or ""
            import_name = f"{'.' * level}{module}" if level > 0 else module
            if import_name:
                imports.append(import_name)
                file_tokens.update(TOKEN_RE.findall(import_name.lower()))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = str(node.name)
        start_line = int(getattr(node, "lineno", 0) or 0)
        end_line = int(getattr(node, "end_lineno", start_line) or start_line)
        calls: list[str] = []
        token_set: set[str] = {name.lower()}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                callee = _python_call_name(sub)
                if callee:
                    calls.append(callee)
                    token_set.add(callee.lower())
            elif isinstance(sub, ast.Name):
                token_set.add(sub.id.lower())
            elif isinstance(sub, ast.Attribute):
                token_set.add(sub.attr.lower())

        fn_source = _python_function_source(text, node)
        norm = _normalize_python_body(fn_source)
        body_hash = _sha1(norm) if norm else ""
        complexity = _python_cyclomatic(node)
        uid = f"{rel_path}::{name}:{start_line}"

        functions.append(
            FunctionInfo(
                uid=uid,
                file_path=file_path,
                rel_path=rel_path,
                name=name,
                start_line=start_line,
                end_line=end_line,
                language="python",
                complexity=complexity,
                calls=calls,
                token_set=token_set,
                body_hash=body_hash,
            )
        )
        file_tokens.update(token_set)

    return imports, functions, file_tokens


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            starts.append(idx + 1)
    return starts


def _line_for_offset(starts: list[int], offset: int) -> int:
    if offset < 0:
        return 1
    return bisect.bisect_right(starts, offset)


def _find_matching_brace(text: str, open_brace_idx: int) -> int:
    depth = 0
    i = open_brace_idx
    in_string: str | None = None
    in_line_comment = False
    in_block_comment = False
    escaped = False
    length = len(text)

    while i < length:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < length else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string is not None:
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch in {"'", '"', "`"}:
            in_string = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1

    return length - 1


def _js_calls(text: str, *, limit: int = 200) -> list[str]:
    calls: list[str] = []
    for call in JS_CALL_RE.findall(text):
        if call in JS_CALL_KEYWORDS:
            continue
        calls.append(call)
        if len(calls) >= limit:
            break
    return calls


def _js_cyclomatic(text: str) -> int:
    score = 1
    score += len(re.findall(r"\bif\b|\bfor\b|\bwhile\b|\bcase\b|\bcatch\b", text))
    score += text.count("&&")
    score += text.count("||")
    score += len(re.findall(r"(?<!\?)\?(?!\.)", text))
    return score


def _parse_js_like_file(
    *,
    file_path: str,
    rel_path: str,
    text: str,
    language: str,
) -> tuple[list[str], list[FunctionInfo], set[str]]:
    imports = JS_IMPORT_RE.findall(text)
    imports.extend(JS_REQUIRE_RE.findall(text))
    file_tokens: set[str] = set()
    for item in imports:
        file_tokens.update(TOKEN_RE.findall(item.lower()))

    candidates: list[tuple[int, str, int]] = []
    for match in JS_FUNC_BLOCK_RE.finditer(text):
        candidates.append((match.start(), match.group(1), match.end() - 1))
    for match in JS_ARROW_BLOCK_RE.finditer(text):
        candidates.append((match.start(), match.group(1), match.end() - 1))
    candidates.sort(key=lambda item: item[0])

    starts = _line_starts(text)
    functions: list[FunctionInfo] = []
    for i, (offset, name, open_brace_idx) in enumerate(candidates, start=1):
        close_brace_idx = _find_matching_brace(text, open_brace_idx)
        body_start = min(open_brace_idx + 1, len(text))
        body_end = max(body_start, close_brace_idx)
        body = text[body_start:body_end]
        start_line = _line_for_offset(starts, offset)
        end_line = _line_for_offset(starts, close_brace_idx)

        calls = _js_calls(body, limit=200)
        complexity = _js_cyclomatic(body)
        token_set = {name.lower()}
        token_set.update(call.lower() for call in calls)
        uid = f"{rel_path}::{name}:{i}"
        functions.append(
            FunctionInfo(
                uid=uid,
                file_path=file_path,
                rel_path=rel_path,
                name=name,
                start_line=start_line,
                end_line=max(end_line, start_line),
                language=language,
                complexity=complexity,
                calls=calls,
                token_set=token_set,
                body_hash=_sha1(f"{name}:{_normalize_js_body(body[:40000])}"),
            )
        )
        file_tokens.update(token_set)

    if not functions:
        calls = _js_calls(text, limit=200)
        token_set = set(call.lower() for call in calls)
        functions.append(
            FunctionInfo(
                uid=f"{rel_path}::file_scope:1",
                file_path=file_path,
                rel_path=rel_path,
                name="file_scope",
                start_line=1,
                end_line=max(1, len(starts)),
                language=language,
                complexity=_js_cyclomatic(text),
                calls=calls,
                token_set=token_set,
                body_hash=_sha1(_normalize_js_body(text[:40000])),
            )
        )
        file_tokens.update(token_set)

    return imports, functions, file_tokens


def _internal_import(import_name: str, top_modules: set[str]) -> bool:
    if not import_name:
        return False
    if import_name.startswith("."):
        return True
    return import_name.split(".")[0] in top_modules


def analyze_scan(
    *,
    source_path: str,
    scan_artifact: Path,
    min_file_similarity: float,
    min_function_similarity: float,
    max_file_pairs: int,
    max_function_pairs: int,
    complexity_threshold: int,
    exclude_subpaths: list[str],
    use_default_excludes: bool,
) -> dict[str, Any]:
    source_root = Path(source_path).resolve()
    scan_rows = 0
    missing_files = 0
    skipped_by_filter = 0

    filters: list[str] = []
    if use_default_excludes:
        filters.extend(DEFAULT_EXCLUDE_SUBPATHS)
    filters.extend(token.strip().lower().replace("\\", "/") for token in exclude_subpaths if token.strip())
    file_rows: list[dict[str, Any]] = []
    top_modules: set[str] = set()

    for raw in scan_artifact.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        scan_rows += 1
        obj = json.loads(raw)
        file_path = Path(str(obj.get("path", ""))).resolve()
        ext = str(obj.get("ext", file_path.suffix.lower())).lower()
        file_path_key = str(file_path).lower().replace("\\", "/")
        if filters and any(token in file_path_key for token in filters):
            skipped_by_filter += 1
            continue
        if ext not in {".py", ".js", ".ts"}:
            continue
        if not file_path.exists() or not file_path.is_file():
            missing_files += 1
            continue
        try:
            rel = file_path.relative_to(source_root).as_posix()
        except ValueError:
            rel = file_path.name

        if ext == ".py":
            module = _module_from_rel_path(rel)
            if module:
                top_modules.add(module.split(".")[0])
        file_rows.append(
            {
                "path": str(file_path),
                "rel_path": rel,
                "ext": ext,
            }
        )

    dependency_counter: Counter[tuple[str, str]] = Counter()
    function_infos: list[FunctionInfo] = []
    file_token_sets: dict[str, set[str]] = {}

    for row in file_rows:
        file_path = str(row["path"])
        rel_path = str(row["rel_path"])
        ext = str(row["ext"])
        text = _safe_read_text(Path(file_path))
        if ext == ".py":
            imports, functions, file_tokens = _parse_python_file(file_path=file_path, rel_path=rel_path, text=text)
        else:
            language = "typescript" if ext == ".ts" else "javascript"
            imports, functions, file_tokens = _parse_js_like_file(
                file_path=file_path,
                rel_path=rel_path,
                text=text,
                language=language,
            )
        for import_name in imports:
            dependency_counter[(file_path, import_name)] += 1
        function_infos.extend(functions)
        file_token_sets[file_path] = file_tokens

    name_to_function_uids: dict[str, list[str]] = defaultdict(list)
    for fn in function_infos:
        name_to_function_uids[fn.name].append(fn.uid)

    call_counter: Counter[tuple[str, str, str, int, str]] = Counter()
    resolved_call_graph: dict[str, set[str]] = defaultdict(set)
    for fn in function_infos:
        callee_counts = Counter(fn.calls)
        for callee_name, count in callee_counts.items():
            targets = name_to_function_uids.get(callee_name, [])
            is_internal = 1 if targets else 0
            callee_uid = targets[0] if len(targets) == 1 else ""
            call_counter[(fn.uid, fn.file_path, callee_name, is_internal, callee_uid)] += int(count)
            if callee_uid:
                resolved_call_graph[fn.uid].add(callee_uid)

    def _max_depth() -> int:
        memo: dict[str, int] = {}
        visiting: set[str] = set()

        def depth(node_id: str) -> int:
            if node_id in memo:
                return memo[node_id]
            if node_id in visiting:
                return 0
            visiting.add(node_id)
            best = 0
            for nxt in resolved_call_graph.get(node_id, set()):
                best = max(best, 1 + depth(nxt))
            visiting.discard(node_id)
            memo[node_id] = best
            return best

        overall = 0
        for node_id in resolved_call_graph:
            overall = max(overall, depth(node_id))
        return overall

    max_call_chain_depth = _max_depth()

    function_pairs: list[dict[str, Any]] = []
    pair_seen: set[tuple[str, str]] = set()
    hash_groups: dict[str, list[FunctionInfo]] = defaultdict(list)
    for fn in function_infos:
        if fn.body_hash:
            hash_groups[fn.body_hash].append(fn)

    for group in hash_groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda x: x.uid)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                left = ordered[i].uid
                right = ordered[j].uid
                if (left, right) in pair_seen:
                    continue
                pair_seen.add((left, right))
                function_pairs.append(
                    {
                        "left_id": left,
                        "right_id": right,
                        "similarity": 1.0,
                        "evidence": {"mode": "exact_hash"},
                    }
                )

    fn_signatures = {fn.uid: _minhash_signature(fn.token_set) for fn in function_infos if fn.token_set}
    fn_by_uid = {fn.uid: fn for fn in function_infos}
    for left, right in _signature_candidates(fn_signatures):
        if (left, right) in pair_seen:
            continue
        a = fn_by_uid[left].token_set
        b = fn_by_uid[right].token_set
        sim = _jaccard(a, b)
        if sim < min_function_similarity:
            continue
        pair_seen.add((left, right))
        function_pairs.append(
            {
                "left_id": left,
                "right_id": right,
                "similarity": round(sim, 6),
                "evidence": {"mode": "token_jaccard"},
            }
        )

    function_pairs.sort(key=lambda x: (-float(x["similarity"]), str(x["left_id"]), str(x["right_id"])))
    function_pairs = function_pairs[:max_function_pairs]

    file_pairs: list[dict[str, Any]] = []
    file_signatures = {path: _minhash_signature(tokens) for path, tokens in file_token_sets.items() if tokens}
    file_candidates = _signature_candidates(file_signatures)
    for left, right in file_candidates:
        sim = _jaccard(file_token_sets[left], file_token_sets[right])
        if sim < min_file_similarity:
            continue
        file_pairs.append(
            {
                "left_id": left,
                "right_id": right,
                "similarity": round(sim, 6),
                "evidence": {"mode": "token_jaccard"},
            }
        )
    file_pairs.sort(key=lambda x: (-float(x["similarity"]), str(x["left_id"]), str(x["right_id"])))
    file_pairs = file_pairs[:max_file_pairs]

    complexity_values = [fn.complexity for fn in function_infos]
    p95 = 0.0
    if complexity_values:
        sorted_vals = sorted(complexity_values)
        idx = min(len(sorted_vals) - 1, int(0.95 * (len(sorted_vals) - 1)))
        p95 = float(sorted_vals[idx])

    dependency_rows = [
        {
            "file_path": file_path,
            "import_name": import_name,
            "is_internal": int(_internal_import(import_name, top_modules)),
            "import_count": int(count),
        }
        for (file_path, import_name), count in dependency_counter.items()
    ]
    dependency_rows.sort(key=lambda x: (-int(x["import_count"]), str(x["file_path"]), str(x["import_name"])))

    call_rows = [
        {
            "caller_uid": caller_uid,
            "caller_file": caller_file,
            "callee_name": callee_name,
            "is_internal": int(is_internal),
            "callee_uid": callee_uid,
            "call_count": int(count),
        }
        for (caller_uid, caller_file, callee_name, is_internal, callee_uid), count in call_counter.items()
    ]
    call_rows.sort(key=lambda x: (-int(x["call_count"]), str(x["caller_uid"]), str(x["callee_name"])))

    complexity_rows = [
        {
            "file_path": fn.file_path,
            "function_uid": fn.uid,
            "function_name": fn.name,
            "start_line": int(fn.start_line),
            "end_line": int(fn.end_line),
            "language": fn.language,
            "cyclomatic": int(fn.complexity),
            "call_count": int(len(fn.calls)),
        }
        for fn in function_infos
    ]
    complexity_rows.sort(key=lambda x: (-int(x["cyclomatic"]), str(x["function_uid"])))

    summary = {
        "scan_rows": scan_rows,
        "files_analyzed": len(file_rows),
        "functions_analyzed": len(function_infos),
        "dependency_edges": len(dependency_rows),
        "call_edges": len(call_rows),
        "internal_call_edges": sum(1 for row in call_rows if int(row["is_internal"]) == 1),
        "avg_cyclomatic": round(mean(complexity_values), 4) if complexity_values else 0.0,
        "max_cyclomatic": max(complexity_values) if complexity_values else 0,
        "p95_cyclomatic": p95,
        "high_complexity_functions": sum(1 for c in complexity_values if c >= complexity_threshold),
        "file_similarity_pairs": len(file_pairs),
        "function_similarity_pairs": len(function_pairs),
        "max_call_chain_depth": int(max_call_chain_depth),
        "missing_files": missing_files,
        "skipped_by_filter": skipped_by_filter,
    }

    return {
        "summary": summary,
        "dependencies": dependency_rows,
        "calls": call_rows,
        "complexity": complexity_rows,
        "file_pairs": file_pairs,
        "function_pairs": function_pairs,
    }


def _ensure_tables(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_project_intelligence (
          source_path TEXT PRIMARY KEY,
          source_project TEXT NOT NULL,
          files_analyzed INTEGER NOT NULL,
          functions_analyzed INTEGER NOT NULL,
          dependency_edges INTEGER NOT NULL,
          call_edges INTEGER NOT NULL,
          internal_call_edges INTEGER NOT NULL,
          avg_cyclomatic REAL NOT NULL,
          max_cyclomatic INTEGER NOT NULL,
          p95_cyclomatic REAL NOT NULL,
          high_complexity_functions INTEGER NOT NULL,
          file_similarity_pairs INTEGER NOT NULL,
          function_similarity_pairs INTEGER NOT NULL,
          max_call_chain_depth INTEGER NOT NULL,
          scan_artifact TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_dependency_edges (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL,
          source_project TEXT NOT NULL,
          file_path TEXT NOT NULL,
          import_name TEXT NOT NULL,
          is_internal INTEGER NOT NULL,
          import_count INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_path, file_path, import_name)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_call_edges (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL,
          source_project TEXT NOT NULL,
          caller_uid TEXT NOT NULL,
          caller_file TEXT NOT NULL,
          callee_name TEXT NOT NULL,
          callee_uid TEXT NOT NULL,
          is_internal INTEGER NOT NULL,
          call_count INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_path, caller_uid, callee_name, callee_uid)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_complexity_nodes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL,
          source_project TEXT NOT NULL,
          file_path TEXT NOT NULL,
          function_uid TEXT NOT NULL,
          function_name TEXT NOT NULL,
          start_line INTEGER NOT NULL,
          end_line INTEGER NOT NULL,
          language TEXT NOT NULL,
          cyclomatic INTEGER NOT NULL,
          call_count INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_path, function_uid)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codegraphx_similarity_pairs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL,
          source_project TEXT NOT NULL,
          pair_type TEXT NOT NULL,
          left_id TEXT NOT NULL,
          right_id TEXT NOT NULL,
          similarity REAL NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_path, pair_type, left_id, right_id)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_intel_source_project ON codegraphx_project_intelligence (source_project)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_dep_source_internal ON codegraphx_dependency_edges (source_path, is_internal)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_call_source_internal ON codegraphx_call_edges (source_path, is_internal)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_call_caller ON codegraphx_call_edges (caller_uid)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_complexity_source_score ON codegraphx_complexity_nodes (source_path, cyclomatic)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_similarity_source_type ON codegraphx_similarity_pairs (source_path, pair_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_similarity_score ON codegraphx_similarity_pairs (similarity)")


def persist_results(
    conn: sqlite3.Connection,
    *,
    source_path: str,
    source_project: str,
    scan_artifact: Path,
    results: dict[str, Any],
    replace_existing: bool,
) -> None:
    cur = conn.cursor()
    _ensure_tables(cur)

    if replace_existing:
        cur.execute("DELETE FROM codegraphx_dependency_edges WHERE source_path=?", (source_path,))
        cur.execute("DELETE FROM codegraphx_call_edges WHERE source_path=?", (source_path,))
        cur.execute("DELETE FROM codegraphx_complexity_nodes WHERE source_path=?", (source_path,))
        cur.execute("DELETE FROM codegraphx_similarity_pairs WHERE source_path=?", (source_path,))

    cur.executemany(
        """
        INSERT INTO codegraphx_dependency_edges (
          source_path, source_project, file_path, import_name, is_internal, import_count
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path, file_path, import_name) DO UPDATE SET
          source_project=excluded.source_project,
          is_internal=excluded.is_internal,
          import_count=excluded.import_count,
          updated_at=CURRENT_TIMESTAMP
        """,
        [
            (
                source_path,
                source_project,
                str(row["file_path"]),
                str(row["import_name"]),
                int(row["is_internal"]),
                int(row["import_count"]),
            )
            for row in results["dependencies"]
        ],
    )
    cur.executemany(
        """
        INSERT INTO codegraphx_call_edges (
          source_path, source_project, caller_uid, caller_file, callee_name, callee_uid, is_internal, call_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path, caller_uid, callee_name, callee_uid) DO UPDATE SET
          source_project=excluded.source_project,
          caller_file=excluded.caller_file,
          is_internal=excluded.is_internal,
          call_count=excluded.call_count,
          updated_at=CURRENT_TIMESTAMP
        """,
        [
            (
                source_path,
                source_project,
                str(row["caller_uid"]),
                str(row["caller_file"]),
                str(row["callee_name"]),
                str(row["callee_uid"]),
                int(row["is_internal"]),
                int(row["call_count"]),
            )
            for row in results["calls"]
        ],
    )
    cur.executemany(
        """
        INSERT INTO codegraphx_complexity_nodes (
          source_path, source_project, file_path, function_uid, function_name,
          start_line, end_line, language, cyclomatic, call_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path, function_uid) DO UPDATE SET
          source_project=excluded.source_project,
          file_path=excluded.file_path,
          function_name=excluded.function_name,
          start_line=excluded.start_line,
          end_line=excluded.end_line,
          language=excluded.language,
          cyclomatic=excluded.cyclomatic,
          call_count=excluded.call_count,
          updated_at=CURRENT_TIMESTAMP
        """,
        [
            (
                source_path,
                source_project,
                str(row["file_path"]),
                str(row["function_uid"]),
                str(row["function_name"]),
                int(row["start_line"]),
                int(row["end_line"]),
                str(row["language"]),
                int(row["cyclomatic"]),
                int(row["call_count"]),
            )
            for row in results["complexity"]
        ],
    )
    similarity_rows = (
        [("file", row) for row in results["file_pairs"]] + [("function", row) for row in results["function_pairs"]]
    )
    cur.executemany(
        """
        INSERT INTO codegraphx_similarity_pairs (
          source_path, source_project, pair_type, left_id, right_id, similarity, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path, pair_type, left_id, right_id) DO UPDATE SET
          source_project=excluded.source_project,
          similarity=excluded.similarity,
          evidence_json=excluded.evidence_json,
          updated_at=CURRENT_TIMESTAMP
        """,
        [
            (
                source_path,
                source_project,
                pair_type,
                str(row["left_id"]),
                str(row["right_id"]),
                float(row["similarity"]),
                json.dumps(row["evidence"], ensure_ascii=False),
            )
            for pair_type, row in similarity_rows
        ],
    )

    summary = results["summary"]
    cur.execute(
        """
        INSERT INTO codegraphx_project_intelligence (
          source_path, source_project, files_analyzed, functions_analyzed,
          dependency_edges, call_edges, internal_call_edges,
          avg_cyclomatic, max_cyclomatic, p95_cyclomatic,
          high_complexity_functions, file_similarity_pairs, function_similarity_pairs,
          max_call_chain_depth, scan_artifact
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path) DO UPDATE SET
          source_project=excluded.source_project,
          files_analyzed=excluded.files_analyzed,
          functions_analyzed=excluded.functions_analyzed,
          dependency_edges=excluded.dependency_edges,
          call_edges=excluded.call_edges,
          internal_call_edges=excluded.internal_call_edges,
          avg_cyclomatic=excluded.avg_cyclomatic,
          max_cyclomatic=excluded.max_cyclomatic,
          p95_cyclomatic=excluded.p95_cyclomatic,
          high_complexity_functions=excluded.high_complexity_functions,
          file_similarity_pairs=excluded.file_similarity_pairs,
          function_similarity_pairs=excluded.function_similarity_pairs,
          max_call_chain_depth=excluded.max_call_chain_depth,
          scan_artifact=excluded.scan_artifact,
          updated_at=CURRENT_TIMESTAMP
        """,
        (
            source_path,
            source_project,
            int(summary["files_analyzed"]),
            int(summary["functions_analyzed"]),
            int(summary["dependency_edges"]),
            int(summary["call_edges"]),
            int(summary["internal_call_edges"]),
            float(summary["avg_cyclomatic"]),
            int(summary["max_cyclomatic"]),
            float(summary["p95_cyclomatic"]),
            int(summary["high_complexity_functions"]),
            int(summary["file_similarity_pairs"]),
            int(summary["function_similarity_pairs"]),
            int(summary["max_call_chain_depth"]),
            str(scan_artifact),
        ),
    )
    conn.commit()


def _render_text(summary: dict[str, Any]) -> str:
    lines = [
        "Code Intelligence Signals",
        "=========================",
        f"source_project: {summary['source_project']}",
        f"source_path: {summary['source_path']}",
        f"scan_artifact: {summary['scan_artifact']}",
        f"files_analyzed: {summary['files_analyzed']}",
        f"functions_analyzed: {summary['functions_analyzed']}",
        f"dependency_edges: {summary['dependency_edges']}",
        f"call_edges: {summary['call_edges']}",
        f"internal_call_edges: {summary['internal_call_edges']}",
        f"avg_cyclomatic: {summary['avg_cyclomatic']}",
        f"max_cyclomatic: {summary['max_cyclomatic']}",
        f"p95_cyclomatic: {summary['p95_cyclomatic']}",
        f"high_complexity_functions: {summary['high_complexity_functions']}",
        f"file_similarity_pairs: {summary['file_similarity_pairs']}",
        f"function_similarity_pairs: {summary['function_similarity_pairs']}",
        f"max_call_chain_depth: {summary['max_call_chain_depth']}",
        f"missing_files: {summary['missing_files']}",
        f"skipped_by_filter: {summary['skipped_by_filter']}",
        f"db_updated: {summary['db_updated']}",
    ]
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    if args.max_file_pairs < 1 or args.max_func_pairs < 1:
        raise SystemExit("max pair limits must be >= 1")
    if args.min_file_sim < 0 or args.min_file_sim > 1 or args.min_func_sim < 0 or args.min_func_sim > 1:
        raise SystemExit("similarity thresholds must be in [0, 1]")

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    source_path = _normalize_path(args.source_path)
    source_project = args.source_project or Path(source_path).name

    conn = sqlite3.connect(str(db_path))
    try:
        scan_artifact, source_project_db = _resolve_scan_artifact(
            conn,
            source_path=source_path,
            scan_override=args.scan,
        )
        if not args.source_project and source_project_db:
            source_project = source_project_db

        exclude_subpaths = [x.strip() for x in args.exclude_subpath.split(",") if x.strip()]
        results = analyze_scan(
            source_path=source_path,
            scan_artifact=scan_artifact,
            min_file_similarity=float(args.min_file_sim),
            min_function_similarity=float(args.min_func_sim),
            max_file_pairs=int(args.max_file_pairs),
            max_function_pairs=int(args.max_func_pairs),
            complexity_threshold=int(args.complexity_threshold),
            exclude_subpaths=exclude_subpaths,
            use_default_excludes=not bool(args.no_default_excludes),
        )

        if not args.dry_run:
            persist_results(
                conn,
                source_path=source_path,
                source_project=source_project,
                scan_artifact=scan_artifact,
                results=results,
                replace_existing=not args.append,
            )
    finally:
        conn.close()

    summary = {
        "status": "completed",
        "source_path": source_path,
        "source_project": source_project,
        "scan_artifact": str(scan_artifact),
        **results["summary"],
        "db_updated": not args.dry_run,
        "append_mode": bool(args.append),
    }
    output = json.dumps(summary, indent=2) if args.json else _render_text(summary)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
