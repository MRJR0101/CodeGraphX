from __future__ import annotations

from pathlib import Path
from typing import Any

from codegraphx.cli.commands import search
from codegraphx.core.io import write_jsonl
from codegraphx.core.search_index import build_search_index, query_search_index


def test_search_project_filter_matches_file_nodes_without_explicit_project(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class _Cfg:
        out_dir = tmp_path / "out"

    monkeypatch.setattr(search, "load_settings", lambda _path: _Cfg())
    monkeypatch.setattr(
        search,
        "read_jsonl",
        lambda _path: [
            {
                "kind": "node",
                "label": "File",
                "uid": "Demo:m.py",
                "props": {
                    "uid": "Demo:m.py",
                    "path": r"C:\repo\m.py",
                    "rel_path": "m.py",
                    "language": "python",
                    "line_count": 2,
                },
            }
        ],
    )
    monkeypatch.setattr(
        search,
        "print_rows",
        lambda _title, rows, limit=20: captured.update({"rows": rows, "limit": limit}),
    )

    search.command("m.py", project="Demo", index="all", limit=20, settings="config/default.yaml")

    assert captured["rows"] == [
        {
            "label": "File",
            "uid": "Demo:m.py",
            "path": r"C:\repo\m.py",
            "rel_path": "m.py",
            "language": "python",
            "line_count": 2,
        }
    ]


def test_query_search_index_normalizes_punctuation_queries(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    db_path = tmp_path / "search.db"
    write_jsonl(
        events_path,
        [
            {
                "kind": "node",
                "label": "File",
                "uid": "Demo:m.py",
                "props": {
                    "name": "m.py",
                    "path": r"C:\repo\m.py",
                    "project": "Demo",
                    "rel_path": "m.py",
                },
            }
        ],
    )
    build_search_index(events_path, db_path)

    rows = query_search_index(db_path, "m.py", project="Demo")

    assert rows == [
        {
            "label": "File",
            "uid": "Demo:m.py",
            "name": "m.py",
            "path": r"C:\repo\m.py",
            "project": "Demo",
            "rel_path": "m.py",
        }
    ]


def test_search_falls_back_to_linear_scan_when_index_misses(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class _Cfg:
        out_dir = tmp_path / "out"

    out_dir = _Cfg.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Both files must exist so search() takes the "db exists, query empty -> fall back" branch.
    (out_dir / "search.db").write_text("", encoding="utf-8")
    (out_dir / "events.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(search, "load_settings", lambda _path: _Cfg())
    monkeypatch.setattr(search, "query_search_index", lambda **_kwargs: [])
    monkeypatch.setattr(
        search,
        "read_jsonl",
        lambda _path: [
            {
                "kind": "node",
                "label": "File",
                "uid": "Demo:m.py",
                "props": {
                    "uid": "Demo:m.py",
                    "path": r"C:\repo\m.py",
                    "rel_path": "m.py",
                    "language": "python",
                    "line_count": 2,
                },
            }
        ],
    )
    monkeypatch.setattr(
        search,
        "print_rows",
        lambda _title, rows, limit=20: captured.update({"rows": rows, "limit": limit}),
    )

    search.command("m.py", project="Demo", index="all", limit=20, settings="config/default.yaml")

    assert captured["rows"] == [
        {
            "label": "File",
            "uid": "Demo:m.py",
            "path": r"C:\repo\m.py",
            "rel_path": "m.py",
            "language": "python",
            "line_count": 2,
        }
    ]
