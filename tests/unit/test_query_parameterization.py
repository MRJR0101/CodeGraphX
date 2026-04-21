from __future__ import annotations

from typing import Any

from codegraphx.cli.commands import ask, compare, impact
from codegraphx.graph.neo4j_client import QueryResult, _assert_readonly_cypher


def test_compare_passes_project_params(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run_query(
        _cfg: object,
        cypher: str,
        params: dict[str, Any] | None = None,
        readonly: bool = False,
    ) -> QueryResult:
        captured["cypher"] = cypher
        captured["params"] = params
        captured["readonly"] = readonly
        return QueryResult(columns=[], rows=[])

    monkeypatch.setattr(compare, "load_settings", lambda _path: object())
    monkeypatch.setattr(compare, "run_query", fake_run_query)
    monkeypatch.setattr(compare, "print_rows", lambda *_args, **_kwargs: None)

    compare.command("proj'a", "projb", mode="shared", settings="config/default.yaml")

    assert "$a" in captured["cypher"]
    assert "$b" in captured["cypher"]
    assert captured["params"] == {"a": "proj'a", "b": "projb"}
    assert captured["readonly"] is True


def test_impact_passes_symbol_and_project_params(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run_query(
        _cfg: object,
        cypher: str,
        params: dict[str, Any] | None = None,
        readonly: bool = False,
    ) -> QueryResult:
        calls.append({"cypher": cypher, "params": params, "readonly": readonly})
        return QueryResult(columns=[], rows=[])

    monkeypatch.setattr(impact, "load_settings", lambda _path: object())
    monkeypatch.setattr(impact, "run_query", fake_run_query)
    monkeypatch.setattr(impact, "print_rows", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(impact, "print_kv", lambda *_args, **_kwargs: None)

    impact.command("o'hare", project="demo'a", depth=2, limit=10, settings="config/default.yaml")

    assert len(calls) == 4
    for call in calls:
        assert call["params"] == {"symbol": "o'hare", "project": "demo'a"}
        assert "$symbol" in call["cypher"]
        assert "$project" in call["cypher"]
        assert call["readonly"] is True


def test_ask_translation_returns_parameterized_query(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run_query(
        _cfg: object,
        cypher: str,
        params: dict[str, Any] | None = None,
        readonly: bool = False,
    ) -> QueryResult:
        captured["cypher"] = cypher
        captured["params"] = params
        captured["readonly"] = readonly
        return QueryResult(columns=[], rows=[])

    monkeypatch.setattr(ask, "load_settings", lambda _path: object())
    monkeypatch.setattr(ask, "run_query", fake_run_query)
    monkeypatch.setattr(ask, "print_rows", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ask, "print_kv", lambda *_args, **_kwargs: None)

    ask.command(
        question="show duplicate functions",
        project="proj'a",
        model="openai",
        model_name="gpt-4o",
        settings="config/default.yaml",
    )

    assert "$project" in captured["cypher"]
    assert captured["params"] == {"project": "proj'a"}
    assert captured["readonly"] is True


def test_readonly_query_guard_rejects_write_like_queries() -> None:
    for query in [
        "MATCH (n) RETURN n; DELETE n",
        "/* note */ CREATE (n:Temp)",
        "MATCH (n)\nCALL dbms.procedures()",
        "MATCH (n) FOREACH (_ IN [1] | SET n.flag = true)",
    ]:
        try:
            _assert_readonly_cypher(query)
        except ValueError:
            continue
        raise AssertionError(f"expected readonly guard to reject query: {query}")


def test_readonly_query_guard_allows_simple_read_query() -> None:
    _assert_readonly_cypher("// comment\nMATCH (f:Function)\nWHERE f.project = $project\nRETURN f.name LIMIT 10")
