from __future__ import annotations

import typer

from codegraphx.cli.output import print_rows
from codegraphx.core.config import load_settings
from codegraphx.graph.neo4j_client import run_query


def _compare_query(project_a: str, project_b: str, mode: str) -> str:
    if mode == "shared":
        return (
            "MATCH (fa:Function {project:$a}), (fb:Function {project:$b}) "
            "WHERE fa.name = fb.name "
            "RETURN fa.name AS function, fa.file_uid AS file_a, fb.file_uid AS file_b "
            "ORDER BY function LIMIT 50"
        )
    if mode == "unique-a":
        return (
            "MATCH (fa:Function {project:$a}) "
            "WHERE NOT EXISTS { MATCH (fb:Function {project:$b}) WHERE fb.name = fa.name } "
            "RETURN fa.name AS function, fa.file_uid AS file ORDER BY function LIMIT 50"
        )
    if mode == "unique-b":
        return (
            "MATCH (fb:Function {project:$b}) "
            "WHERE NOT EXISTS { MATCH (fa:Function {project:$a}) WHERE fa.name = fb.name } "
            "RETURN fb.name AS function, fb.file_uid AS file ORDER BY function LIMIT 50"
        )
    if mode == "metrics":
        return (
            "MATCH (f:Function) WHERE f.project IN [$a, $b] "
            "RETURN f.project AS project, count(*) AS function_count "
            "ORDER BY function_count DESC"
        )
    if mode == "patterns":
        return (
            "MATCH (f:Function) WHERE f.project IN [$a, $b] "
            "WITH f.project AS project, "
            "sum(CASE WHEN toLower(f.name) CONTAINS 'factory' THEN 1 ELSE 0 END) AS factories, "
            "sum(CASE WHEN toLower(f.name) CONTAINS 'singleton' THEN 1 ELSE 0 END) AS singletons "
            "RETURN project, factories, singletons ORDER BY project"
        )
    return (
        "MATCH (f:Function) WHERE f.project IN [$a, $b] "
        "RETURN f.project AS project, f.name AS function, f.file_uid AS file "
        "ORDER BY function LIMIT 100"
    )


def command(
    project_a: str = typer.Argument(...),
    project_b: str = typer.Argument(...),
    mode: str = typer.Option("shared", "--mode", "-m", help="shared|unique-a|unique-b|metrics|patterns|calltrees"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    cypher = _compare_query(project_a, project_b, mode)
    result = run_query(cfg, cypher, {"a": project_a, "b": project_b})
    print_rows(f"compare {mode}", result.rows)
