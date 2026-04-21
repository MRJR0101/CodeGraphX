"""search command -- uses SQLite FTS5 index built by the load command.

Falls back to O(n) events.jsonl scan if search.db does not exist yet,
so the command works before the first load.
"""

from __future__ import annotations

import typer

from codegraphx.cli.output import print_rows
from codegraphx.core.config import load_settings
from codegraphx.core.io import read_jsonl
from codegraphx.core.search_index import query_search_index
from codegraphx.core.stages import data_paths


def _node_project(label: str, props: dict[str, object]) -> str:
    project = str(props.get("project", "")).strip()
    if project:
        return project
    if label == "Project":
        return str(props.get("name", "")).strip()
    uid = str(props.get("uid", "")).strip()
    if label in {"File", "Function"} and ":" in uid:
        return uid.split(":", 1)[0]
    return ""


def _linear_search(
    events_path: object,
    q: str,
    index: str,
    project: str,
    limit: int,
) -> list[dict[str, object]]:
    """O(n) fallback used before search.db exists."""
    from pathlib import Path
    rows = []
    for ev in read_jsonl(Path(str(events_path))):
        if ev.get("kind") != "node":
            continue
        label = str(ev.get("label", ""))
        props = ev.get("props", {})
        if not isinstance(props, dict):
            continue
        text = str(props.get("name", "")) + " " + str(props.get("path", ""))
        if q not in text.lower():
            continue
        if index == "functions" and label != "Function":
            continue
        if index == "symbols" and label not in {"Symbol", "Module"}:
            continue
        if project and _node_project(label, props) != project:
            continue
        rows.append({"label": label, **props})
        if len(rows) >= limit:
            break
    return rows


def command(
    query: str = typer.Argument(..., help="Search query"),
    project: str = typer.Option("", "--project", "-p", help="Project filter"),
    index: str = typer.Option("all", "--index", "-i", help="all|functions|symbols"),
    limit: int = typer.Option(20, "--limit", "-l", help="Result limit"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    paths = data_paths(cfg)

    if paths.search_db.exists():
        rows = query_search_index(
            db_path=paths.search_db,
            query=query,
            index=index,
            project=project,
            limit=limit,
        )
        if not rows and paths.events.exists():
            rows = _linear_search(
                events_path=paths.events,
                q=query.lower().strip(),
                index=index,
                project=project,
                limit=limit,
            )
    else:
        rows = _linear_search(
            events_path=paths.events,
            q=query.lower().strip(),
            index=index,
            project=project,
            limit=limit,
        )

    print_rows("search result", rows, limit=limit)
