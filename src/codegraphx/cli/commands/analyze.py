from __future__ import annotations

import json
from pathlib import Path

import typer

from codegraphx.cli.output import print_rows
from codegraphx.core.config import load_settings
from codegraphx.graph.neo4j_client import run_query


app = typer.Typer(help="Analysis commands")


@app.command("metrics")
def metrics(
    project: str = typer.Option("", "--project", "-p"),
    limit: int = typer.Option(20, "--limit", "-l"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "OPTIONAL MATCH (f)<-[:CALLS]-(inbound) "
        "OPTIONAL MATCH (f)-[:CALLS]->(outbound) "
        "RETURN f.name AS function, count(DISTINCT inbound) AS fan_in, count(DISTINCT outbound) AS fan_out "
        f"ORDER BY (count(DISTINCT inbound) + count(DISTINCT outbound)) DESC LIMIT {limit}"
    )
    print_rows("analyze metrics", run_query(cfg, cypher, {"project": project}).rows)


@app.command("hotspots")
def hotspots(
    project: str = typer.Option("", "--project", "-p"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "RETURN f.project AS project, f.name AS function, f.line AS line "
        "ORDER BY f.line DESC LIMIT 25"
    )
    print_rows("analyze hotspots", run_query(cfg, cypher, {"project": project}).rows)


@app.command("security")
def security(
    project: str = typer.Option("", "--project", "-p"),
    category: str = typer.Option("", "--category", "-c"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "AND ($category = '' OR toLower(f.name) CONTAINS $category) "
        "RETURN f.project AS project, f.name AS function, f.file_uid AS file "
        "ORDER BY function LIMIT 50"
    )
    print_rows(
        "analyze security",
        run_query(cfg, cypher, {"project": project, "category": category.lower()}).rows,
    )


@app.command("debt")
def debt(
    project: str = typer.Option("", "--project", "-p"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "WITH f.project AS project, count(*) AS functions "
        "RETURN project, functions, round(functions * 0.3, 2) AS debt_score"
    )
    print_rows("analyze debt", run_query(cfg, cypher, {"project": project}).rows)


@app.command("refactor")
def refactor(
    project: str = typer.Option("", "--project", "-p"),
    type: str = typer.Option("", "--type", "-t"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "AND ($type = '' OR toLower(f.name) CONTAINS $type) "
        "RETURN f.project AS project, f.name AS function, f.file_uid AS file "
        "ORDER BY function LIMIT 50"
    )
    print_rows("analyze refactor", run_query(cfg, cypher, {"project": project, "type": type.lower()}).rows)


@app.command("duplicates")
def duplicates(
    limit: int = typer.Option(20, "--limit", "-l"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)
    cypher = (
        "MATCH (f:Function) "
        "WITH f.signature_hash AS signature_hash, collect(f.name) AS names, count(*) AS copies "
        "WHERE copies > 1 "
        f"RETURN signature_hash, copies, names ORDER BY copies DESC LIMIT {limit}"
    )
    print_rows("analyze duplicates", run_query(cfg, cypher).rows)


@app.command("patterns")
def patterns(
    type: str = typer.Option("all", "--type", "-t"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)
    if type == "all":
        predicates = [
            "toLower(f.name) CONTAINS 'factory'",
            "toLower(f.name) CONTAINS 'singleton'",
            "toLower(f.name) CONTAINS 'observer'",
            "toLower(f.name) CONTAINS 'repository'",
            "toLower(f.name) CONTAINS 'plugin'",
        ]
        where = " OR ".join(predicates)
        params: dict[str, str] | None = None
    else:
        where = "toLower(f.name) CONTAINS $pattern"
        params = {"pattern": type.lower().rstrip("s")}
    cypher = (
        "MATCH (f:Function) "
        f"WHERE {where} "
        "RETURN f.project AS project, f.name AS function, f.file_uid AS file "
        "ORDER BY function LIMIT 100"
    )
    print_rows("analyze patterns", run_query(cfg, cypher, params).rows)


@app.command("full")
def full(
    project: str = typer.Option("", "--project", "-p"),
    output: str = typer.Option("", "--output", "-o"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cfg = load_settings(settings)

    queries = {
        "metrics": (
            "MATCH (f:Function) "
            "WHERE ($project = '' OR f.project = $project) "
            "RETURN count(*) AS functions"
        ),
        "duplicates": (
            "MATCH (f:Function) "
            "WHERE ($project = '' OR f.project = $project) "
            "WITH f.signature_hash AS signature_hash, count(*) AS copies "
            "WHERE copies > 1 RETURN count(*) AS duplicate_groups"
        ),
        "patterns": (
            "MATCH (f:Function) "
            "WHERE ($project = '' OR f.project = $project) "
            "AND (toLower(f.name) CONTAINS 'factory' OR toLower(f.name) CONTAINS 'singleton') "
            "RETURN count(*) AS pattern_hits"
        ),
    }

    report: dict[str, list[dict[str, object]]] = {}
    for key, cypher in queries.items():
        report[key] = run_query(cfg, cypher, {"project": project}).rows

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for section, rows in report.items():
        print_rows(f"analyze full: {section}", rows)
