"""Python source file parser for codegraphx.

Provides parse_python(file_text) -> ParseResult.

Uses tree-sitter when available, falls back to stdlib ast.
ParseResult = tuple[functions, imports, calls, function_calls, line_count]
"""

from __future__ import annotations

import ast
import re
from typing import Any, Iterable

_tslp: Any = None
try:
    import tree_sitter_language_pack as _tslp_mod
    _tslp = _tslp_mod
except Exception:  # noqa: BLE001
    _tslp = None

PY_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+))"
)
_PY_TS_PARSER: Any = _tslp.get_parser("python") if _tslp is not None else None

ParseResult = tuple[
    list[dict[str, Any]],  # functions
    list[str],             # imports
    list[str],             # calls
    list[dict[str, Any]],  # function_calls
    int,                   # line_count
]


def _walk_no_nested_fns(node: ast.AST) -> Iterable[ast.AST]:
    """Yield AST nodes without descending into nested function definitions.

    This mirrors tree-sitter behaviour: calls inside an inner function are
    attributed to that inner function, not to the enclosing one.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield from _walk_no_nested_fns(child)


def _parse_python_with_treesitter(file_text: str) -> ParseResult:
    src = file_text.encode("utf-8", errors="ignore")
    if _PY_TS_PARSER is None:
        raise RuntimeError("tree-sitter python parser unavailable")

    tree = _PY_TS_PARSER.parse(src)
    root = tree.root_node

    functions: list[dict[str, Any]] = []
    calls: list[str] = []
    function_calls: list[dict[str, Any]] = []

    def node_text(node: Any) -> str:
        return src[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def call_name(node: Any) -> str:
        text = node_text(node).strip()
        if "." in text:
            text = text.split(".")[-1]
        return text.split("(")[0].strip()

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
                    if child is not node and child.type in {
                        "function_definition", "async_function_definition"
                    }:
                        continue
                    if child.type == "call":
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
        stack.extend(reversed(node.children))

    imports: list[str] = []
    for line in file_text.splitlines():
        m = PY_IMPORT_RE.match(line)
        if m:
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


def _parse_python_with_ast(file_text: str) -> ParseResult:
    try:
        tree = ast.parse(file_text)
    except SyntaxError:
        return [], [], [], [], len(file_text.splitlines())

    functions: list[dict[str, Any]] = []
    imports: list[str] = []
    calls: list[str] = []
    function_calls: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": node.name, "line": node.lineno})
            fn_calls: list[str] = []
            for child in _walk_no_nested_fns(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Name):
                        fn_calls.append(fn.id)
                    elif isinstance(fn, ast.Attribute):
                        fn_calls.append(fn.attr)
            function_calls.append({
                "name": node.name,
                "line": node.lineno,
                "calls": sorted(set(fn_calls)),
            })
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


def parse_python(file_text: str) -> ParseResult:
    """Parse a Python source file. Uses tree-sitter when available, falls back to ast."""
    if _PY_TS_PARSER is not None:
        try:
            return _parse_python_with_treesitter(file_text)
        except Exception:  # noqa: BLE001
            pass
    return _parse_python_with_ast(file_text)
