from __future__ import annotations

from codegraphx.cli.commands.delta import _changed_files, _changed_functions, _parse_identity, _summarize_categories


def test_parse_identity_function_node() -> None:
    ident = "node:Function:DemoA:a.py:add:1"
    parsed = _parse_identity(ident)
    assert parsed["kind"] == "node"
    assert parsed["type"] == "Function"
    assert parsed["project"] == "DemoA"
    assert parsed["file"] == "a.py"
    assert parsed["function"] == "add"
    assert parsed["line"] == "1"


def test_summarize_categories() -> None:
    diff = {
        "added": ["node:Function:DemoA:a.py:add:1", "edge:CALLS:Function:x:Symbol:y"],
        "removed": ["node:File:DemoB:b.py"],
        "changed": ["node:Function:DemoB:b.py:run:9"],
    }
    rows = _summarize_categories(diff)
    keys = {(r["change"], r["category"], r["count"]) for r in rows}
    assert ("added", "node:Function", 1) in keys
    assert ("added", "edge:CALLS", 1) in keys
    assert ("removed", "node:File", 1) in keys
    assert ("changed", "node:Function", 1) in keys


def test_changed_lists_filter_only_node_types() -> None:
    diff = {
        "added": ["node:Function:DemoA:a.py:add:1", "edge:CALLS:Function:x:Symbol:y"],
        "removed": ["node:File:DemoB:b.py"],
        "changed": ["node:Function:DemoB:b.py:run:9"],
    }
    fn_rows = _changed_functions(diff)
    file_rows = _changed_files(diff)
    assert len(fn_rows) == 2
    assert len(file_rows) == 1
    assert fn_rows[0]["project"] in {"DemoA", "DemoB"}
    assert file_rows[0]["project"] == "DemoB"
