"""JavaScript/TypeScript source file parser for codegraphx.

Provides parse_js(ext, file_text) -> ParseResult.

Uses tree-sitter when available, falls back to regex.
ParseResult = tuple[functions, imports, calls, function_calls, line_count]
"""

from __future__ import annotations

import re
from typing import Any

_tslp: Any = None
try:
    import tree_sitter_language_pack as _tslp_mod
    _tslp = _tslp_mod
except Exception:  # noqa: BLE001
    _tslp = None

JS_IMPORT_RE = re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]")
JS_REQUIRE_RE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")
JS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_PY_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")

_JS_TS_PARSER: Any = _tslp.get_parser("javascript") if _tslp is not None else None
_TS_TS_PARSER: Any = _tslp.get_parser("typescript") if _tslp is not None else None

ParseResult = tuple[
    list[dict[str, Any]],
    list[str],
    list[str],
    list[dict[str, Any]],
    int,
]

def _parse_js_like(file_text: str) -> ParseResult:
    """Regex-based fallback parser for JS/TS."""
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
        for call in _PY_CALL_RE.findall(line):
            if call not in {"if", "for", "while", "switch", "return"}:
                calls.append(call)
    return functions, imports, calls, [], len(file_text.splitlines())


def _parse_js_ts_with_treesitter(file_text: str, parser: Any) -> ParseResult:
    src = file_text.encode("utf-8", errors="ignore")
    tree = parser.parse(src)
    root = tree.root_node

    def node_text(node: Any) -> str:
        return src[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def call_name(node: Any) -> str:
        text = node_text(node).strip()
        if "." in text:
            text = text.split(".")[-1]
        return text.split("(")[0].strip()

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
                    if child is not node and child.type in {
                        "function_declaration", "method_definition"
                    }:
                        continue
                    if child.type == "call_expression":
                        fn_node = child.child_by_field_name("function")
                        if fn_node is not None:
                            cn = call_name(fn_node)
                            if cn:
                                fn_calls.append(cn)
                                calls.append(cn)
                    inner_stack.extend(reversed(child.children))
                function_calls.append({
                    "name": fn_name,
                    "line": fn_line,
                    "calls": sorted(set(fn_calls)),
                })

        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node is not None:
                source_text = node_text(source_node).strip().strip("'\"")
                if source_text:
                    imports.append(source_text)

        if node.type == "call_expression":
            fn_node = node.child_by_field_name("function")
            if fn_node is not None and call_name(fn_node) == "require":
                args_node = node.child_by_field_name("arguments")
                if args_node is not None:
                    m = JS_REQUIRE_RE.search(node_text(args_node))
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


def parse_js(ext: str, file_text: str) -> ParseResult:
    """Parse a JS or TS source file. Uses tree-sitter when available, falls back to regex."""
    parser = _JS_TS_PARSER if ext == ".js" else _TS_TS_PARSER
    if parser is not None:
        try:
            return _parse_js_ts_with_treesitter(file_text, parser)
        except Exception:  # noqa: BLE001
            pass
    return _parse_js_like(file_text)
