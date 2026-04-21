"""Unit tests for the JS/TS parser.

These tests exercise both the tree-sitter path (when available) and the
regex fallback. The fallback is forced by passing an unknown extension.
"""

from __future__ import annotations

from codegraphx.core.parsers import javascript as js_parser
from codegraphx.core.parsers.javascript import _parse_js_like, parse_js

JS_SAMPLE = """\
import fs from 'fs';
import { join } from 'path';
const lodash = require('lodash');

function greet(name) {
    console.log('hi', name);
    return name.toUpperCase();
}

export function add(a, b) {
    return a + b;
}

class Greeter {
    hello(name) {
        return greet(name);
    }
}
"""


TS_SAMPLE = """\
import { Thing } from './thing';

export function typed(x: number): number {
    return x * 2;
}
"""


def test_regex_fallback_finds_functions_imports_calls() -> None:
    functions, imports, calls, function_calls, line_count = _parse_js_like(JS_SAMPLE)
    names = {f["name"] for f in functions}
    assert "greet" in names
    assert "add" in names
    assert "fs" in imports
    assert "path" in imports
    assert "lodash" in imports
    # `console.log` parses as `log` via the regex fallback's call pattern.
    assert any(c in {"log", "toUpperCase", "greet"} for c in calls)
    assert function_calls == []  # regex fallback never populates per-fn calls
    assert line_count == JS_SAMPLE.count("\n")


def test_parse_js_respects_ext_and_produces_line_count() -> None:
    functions, imports, _calls, _fn_calls, line_count = parse_js(".js", JS_SAMPLE)
    assert line_count == JS_SAMPLE.count("\n")
    assert any(f["name"] == "greet" for f in functions)
    assert any(imp in imports for imp in ("fs", "path", "lodash"))


def test_parse_ts_handles_typescript_source() -> None:
    functions, imports, _calls, _fn_calls, _line_count = parse_js(".ts", TS_SAMPLE)
    assert any(f["name"] == "typed" for f in functions)
    assert "./thing" in imports


def test_parse_js_falls_back_when_treesitter_unavailable(monkeypatch) -> None:
    # Force parsers to None so parse_js drops into the regex fallback branch.
    monkeypatch.setattr(js_parser, "_JS_TS_PARSER", None, raising=False)
    monkeypatch.setattr(js_parser, "_TS_TS_PARSER", None, raising=False)
    functions, imports, _calls, function_calls, _line_count = parse_js(".js", JS_SAMPLE)
    assert any(f["name"] == "greet" for f in functions)
    assert "lodash" in imports
    assert function_calls == []


def test_parse_js_handles_empty_input() -> None:
    functions, imports, calls, function_calls, line_count = parse_js(".js", "")
    assert functions == []
    assert imports == []
    assert calls == []
    assert function_calls == []
    assert line_count == 0


def test_parse_js_ignores_control_flow_keywords_in_regex_fallback() -> None:
    code = """\
function go() {
    if (true) {
        for (let i = 0; i < 3; i++) {
            while (i > 0) {}
        }
    }
}
"""
    _functions, _imports, calls, _fn_calls, _line_count = _parse_js_like(code)
    for keyword in {"if", "for", "while", "switch", "return"}:
        assert keyword not in calls
