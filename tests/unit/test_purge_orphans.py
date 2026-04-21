from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import purge_orphans


def test_check_impact_requires_graph_evidence(monkeypatch: Any) -> None:
    monkeypatch.setattr(purge_orphans, "load_settings", lambda _path: object())
    monkeypatch.setattr(purge_orphans, "run_query", lambda *_args, **_kwargs: SimpleNamespace(rows=[]))

    assert purge_orphans.check_impact(r"C:\repo\ghost.py") is False


def test_check_impact_accepts_only_zero_caller_files(monkeypatch: Any) -> None:
    monkeypatch.setattr(purge_orphans, "load_settings", lambda _path: object())
    monkeypatch.setattr(
        purge_orphans,
        "run_query",
        lambda *_args, **_kwargs: SimpleNamespace(
            rows=[
                {
                    "matching_files": 1,
                    "definitions": 2,
                    "function_callers": 0,
                    "symbol_callers": 0,
                    "file_callers": 0,
                }
            ]
        ),
    )

    assert purge_orphans.check_impact(r"C:\repo\safe.py") is True
