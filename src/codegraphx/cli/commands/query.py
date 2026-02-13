from __future__ import annotations

from pathlib import Path

import typer

from codegraphx.cli.output import print_rows
from codegraphx.core.config import load_settings
from codegraphx.graph.neo4j_client import run_query


def _resolve_query(cypher_or_file: str) -> str:
    path = Path(cypher_or_file)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return cypher_or_file


def _looks_write_query(cypher: str) -> bool:
    needle = cypher.lower()
    blocked = ("create ", "merge ", "delete ", "set ", "drop ", "remove ", "call dbms", "apoc.")
    return any(token in needle for token in blocked)


def command(
    cypher: str = typer.Argument(..., help="Cypher query string or .cypher file"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    safe: bool = typer.Option(False, help="Reject write operations"),
) -> None:
    cfg = load_settings(settings)
    query = _resolve_query(cypher)
    if safe and _looks_write_query(query):
        raise typer.BadParameter("safe mode rejected write-like query")
    result = run_query(cfg, query)
    print_rows("query result", result.rows)

