from __future__ import annotations

from pathlib import Path
from typing import Mapping

import typer

from codegraphx.cli.output import print_kv, print_rows
from codegraphx.core.churn import (
    compute_churn,
    file_stats_from_events,
    rank_hotspots,
)
from codegraphx.core.config import load_projects, load_settings
from codegraphx.core.io import read_jsonl, write_json
from codegraphx.core.stages import data_paths
from codegraphx.graph.neo4j_client import run_query


app = typer.Typer(help="Analysis commands")


def _query_rows(
    settings: str,
    cypher: str,
    params: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    cfg = load_settings(settings)
    payload = dict(params) if params is not None else None
    return run_query(cfg, cypher, payload, readonly=True).rows


def _emit_section(
    title: str,
    settings: str,
    cypher: str,
    params: Mapping[str, object] | None = None,
) -> None:
    print_rows(title, _query_rows(settings, cypher, params))


@app.command("metrics")
def metrics(
    project: str = typer.Option("", "--project", "-p"),
    limit: int = typer.Option(20, "--limit", "-l"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "OPTIONAL MATCH (f)<-[:CALLS_FUNCTION]-(inbound:Function) "
        "OPTIONAL MATCH (f)-[:CALLS_FUNCTION]->(outbound:Function) "
        "RETURN f.name AS function, count(DISTINCT inbound) AS fan_in, count(DISTINCT outbound) AS fan_out "
        f"ORDER BY (count(DISTINCT inbound) + count(DISTINCT outbound)) DESC LIMIT {limit}"
    )
    _emit_section("analyze metrics", settings, cypher, {"project": project})


@app.command("hotspots")
def hotspots(
    project: str = typer.Option("", "--project", "-p"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "OPTIONAL MATCH (f)<-[:CALLS_FUNCTION]-(inbound:Function) "
        "OPTIONAL MATCH (f)-[:CALLS_FUNCTION]->(outbound:Function) "
        "WITH f, count(DISTINCT inbound) AS fan_in, count(DISTINCT outbound) AS fan_out "
        "RETURN f.project AS project, f.name AS function, f.line AS line, "
        "fan_in, fan_out, (fan_in + fan_out) AS coupling "
        "ORDER BY coupling DESC LIMIT 25"
    )
    _emit_section("analyze hotspots", settings, cypher, {"project": project})


@app.command("churn-hotspots")
def churn_hotspots(
    project: str = typer.Option("", "--project", "-p", help="Restrict to a single project name"),
    since: str = typer.Option("6.months", "--since", help="Git --since expression (e.g. '6.months', '2024-01-01')"),
    top_n: int = typer.Option(25, "--top", "-n", help="Max rows"),
    output: str = typer.Option("", "--output", "-o", help="Optional JSON output path"),
    projects_config: str = typer.Option("config/projects.yaml", "--projects-config", help="Projects config YAML"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    """Rank files by combined graph coupling and recent git churn.

    Reads ``<out_dir>/events.jsonl`` to derive per-file function and edge
    counts, then runs ``git log --numstat`` in each project root to weight
    the ranking by recent churn. No Neo4j connection required.
    """
    cfg = load_settings(settings)
    paths = data_paths(cfg)
    if not paths.events.exists():
        raise typer.BadParameter(
            f"events file not found: {paths.events}. Run `codegraphx pipeline run` first."
        )

    projects_list = load_projects(projects_config)
    if project:
        projects_list = [p for p in projects_list if p.name == project]

    events = read_jsonl(paths.events)
    file_stats = file_stats_from_events(events)
    if project:
        file_stats = [fs for fs in file_stats if fs.get("project") == project]

    churn_by_project = {}
    for proj in projects_list:
        report = compute_churn(project=proj.name, root=proj.root, since=since)
        churn_by_project[proj.name] = report

    ranked = rank_hotspots(file_stats, churn_by_project, top_n=top_n)
    rows = [
        {
            "project": row.project,
            "rel_path": row.rel_path,
            "functions": row.functions,
            "edges": row.edges,
            "commits": row.churn_commits,
            "churn_lines": row.churn_lines,
            "score": row.score,
        }
        for row in ranked
    ]

    print_kv(
        "churn hotspots summary",
        {
            "files_considered": len(file_stats),
            "projects": len(projects_list),
            "since": since,
            "top": len(rows),
        },
    )
    print_rows("analyze churn-hotspots", rows, limit=max(top_n, len(rows)))

    if output:
        write_json(
            Path(output),
            {
                "since": since,
                "project_filter": project,
                "rows": rows,
            },
        )


@app.command("security")
def security(
    project: str = typer.Option("", "--project", "-p"),
    category: str = typer.Option("", "--category", "-c"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "AND ($category = '' OR toLower(f.name) CONTAINS $category) "
        "RETURN f.project AS project, f.name AS function, f.file_uid AS file "
        "ORDER BY function LIMIT 50"
    )
    _emit_section("analyze security", settings, cypher, {"project": project, "category": category.lower()})


@app.command("debt")
def debt(
    project: str = typer.Option("", "--project", "-p"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "WITH f.project AS project, count(*) AS functions "
        "RETURN project, functions, round(functions * 0.3, 2) AS debt_score"
    )
    _emit_section("analyze debt", settings, cypher, {"project": project})


@app.command("refactor")
def refactor(
    project: str = typer.Option("", "--project", "-p"),
    type: str = typer.Option("", "--type", "-t"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cypher = (
        "MATCH (f:Function) "
        "WHERE ($project = '' OR f.project = $project) "
        "AND ($type = '' OR toLower(f.name) CONTAINS $type) "
        "RETURN f.project AS project, f.name AS function, f.file_uid AS file "
        "ORDER BY function LIMIT 50"
    )
    _emit_section("analyze refactor", settings, cypher, {"project": project, "type": type.lower()})


@app.command("duplicates")
def duplicates(
    limit: int = typer.Option(20, "--limit", "-l"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
    cypher = (
        "MATCH (f:Function) "
        "WITH f.signature_hash AS signature_hash, collect(f.name) AS names, count(*) AS copies "
        "WHERE copies > 1 "
        f"RETURN signature_hash, copies, names ORDER BY copies DESC LIMIT {limit}"
    )
    _emit_section("analyze duplicates", settings, cypher)


@app.command("patterns")
def patterns(
    type: str = typer.Option("all", "--type", "-t"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
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
    _emit_section("analyze patterns", settings, cypher, params)


@app.command("full")
def full(
    project: str = typer.Option("", "--project", "-p"),
    output: str = typer.Option("", "--output", "-o"),
    settings: str = typer.Option("config/default.yaml"),
) -> None:
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
        report[key] = _query_rows(settings, cypher, {"project": project})

    if output:
        out_path = Path(output)
        write_json(out_path, report)

    for section, rows in report.items():
        print_rows(f"analyze full: {section}", rows)
