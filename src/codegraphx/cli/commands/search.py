from __future__ import annotations

import typer

from codegraphx.cli.output import print_rows
from codegraphx.core.config import load_settings
from codegraphx.core.io import read_jsonl
from codegraphx.core.stages import data_paths


def command(
    query: str = typer.Argument(..., help="Search query"),
    project: str = typer.Option("", "--project", "-p", help="Project filter"),
    index: str = typer.Option("all", "--index", "-i", help="all|functions|symbols"),
    limit: int = typer.Option(20, "--limit", "-l", help="Result limit"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    events = read_jsonl(data_paths(cfg).events)
    q = query.lower().strip()
    rows = []
    for ev in events:
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
        if project:
            if str(props.get("project", "")) != project:
                continue
        rows.append({"label": label, **props})
        if len(rows) >= limit:
            break
    print_rows("search result", rows, limit=limit)

