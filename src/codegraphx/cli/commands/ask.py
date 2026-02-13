from __future__ import annotations

import typer

from codegraphx.cli.output import print_kv, print_rows
from codegraphx.core.config import load_settings
from codegraphx.graph.neo4j_client import run_query


def _question_to_cypher(question: str, project: str) -> tuple[str, dict[str, str]]:
    q = question.lower()
    params = {"project": project}
    if "duplicate" in q:
        return (
            "MATCH (f:Function) "
            "WHERE ($project = '' OR f.project = $project) "
            "WITH f.signature_hash AS h, collect(f.name) AS names, count(*) AS c "
            "WHERE c > 1 RETURN h, c, names ORDER BY c DESC LIMIT 20",
            params,
        )
    if "entry" in q or "main" in q:
        return (
            "MATCH (f:Function) "
            "WHERE ($project = '' OR f.project = $project) "
            "AND (toLower(f.name) CONTAINS 'main' OR toLower(f.name) CONTAINS 'entry') "
            "RETURN f.name, f.project, f.file_uid LIMIT 20",
            params,
        )
    return (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "RETURN f.name, f.project, f.file_uid ORDER BY f.name LIMIT 20",
        params,
    )


def command(
    question: str = typer.Argument(..., help="Natural language question"),
    project: str = typer.Option("", "--project", "-p", help="Project filter"),
    model: str = typer.Option("openai", "--model", "-m", help="Model provider label"),
    model_name: str = typer.Option("gpt-4o", "--model-name", "-M", help="Model name label"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    cypher, params = _question_to_cypher(question, project)
    result = run_query(cfg, cypher, params)
    print_kv("ask translation", {"model": model, "model_name": model_name, "cypher": cypher, "params": params})
    print_rows("ask result", result.rows)
