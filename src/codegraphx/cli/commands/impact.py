from __future__ import annotations

import typer

from codegraphx.cli.output import print_kv, print_rows
from codegraphx.core.config import load_settings
from codegraphx.graph.neo4j_client import run_query


def command(
    symbol: str = typer.Argument(..., help="Function/symbol name to analyze impact for"),
    project: str = typer.Option("", "--project", "-p", help="Optional project filter"),
    depth: int = typer.Option(3, "--depth", "-d", min=1, max=10, help="Transitive caller depth"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum rows"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    query_params = {"symbol": symbol, "project": project}

    defs_query = (
        "MATCH (f:Function) "
        "WHERE f.name = $symbol AND ($project = '' OR f.project = $project) "
        f"RETURN f.project AS project, f.name AS function, f.file_uid AS file LIMIT {limit}"
    )
    function_callers_query = (
        "MATCH (caller:Function)-[:CALLS]->(s:Symbol) "
        "WHERE s.name = $symbol AND ($project = '' OR caller.project = $project) "
        f"RETURN caller.project AS project, caller.name AS caller, caller.file_uid AS file LIMIT {limit}"
    )
    transitive_callers_query = (
        "MATCH (target:Function) "
        "WHERE target.name = $symbol AND ($project = '' OR target.project = $project) "
        f"MATCH p=(caller:Function)-[:CALLS_FUNCTION*1..{depth}]->(target) "
        "WHERE ($project = '' OR caller.project = $project) "
        "WITH caller, min(length(p)) AS hops "
        f"RETURN caller.project AS project, caller.name AS caller, caller.file_uid AS file, hops "
        f"ORDER BY hops, caller LIMIT {limit}"
    )
    file_callers_query = (
        "MATCH (caller:File)-[:CALLS]->(s:Symbol) "
        "WHERE s.name = $symbol "
        "AND ($project = '' OR coalesce(caller.project, split(caller.uid, ':')[0]) = $project) "
        f"RETURN caller.rel_path AS file, caller.uid AS file_uid LIMIT {limit}"
    )

    defs = run_query(cfg, defs_query, query_params).rows
    function_callers = run_query(cfg, function_callers_query, query_params).rows
    transitive_callers = run_query(cfg, transitive_callers_query, query_params).rows
    file_callers = run_query(cfg, file_callers_query, query_params).rows

    print_kv(
        "impact summary",
        {
            "symbol": symbol,
            "definitions": len(defs),
            "function_callers": len(function_callers),
            "transitive_callers": len(transitive_callers),
            "file_callers": len(file_callers),
            "depth": depth,
        },
    )
    print_rows("impact: definitions", defs, limit=limit)
    print_rows("impact: function callers", function_callers, limit=limit)
    print_rows("impact: transitive callers", transitive_callers, limit=limit)
    print_rows("impact: file callers", file_callers, limit=limit)
