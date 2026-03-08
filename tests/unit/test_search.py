from __future__ import annotations

from pathlib import Path
from typing import Any

from codegraphx.cli.commands import search


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
