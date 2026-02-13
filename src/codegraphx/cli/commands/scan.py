from __future__ import annotations

import typer

from codegraphx.cli.output import print_kv
from codegraphx.core.config import load_projects, load_settings
from codegraphx.core.stages import run_scan


def command(
    config: str = typer.Option("config/projects.yaml", help="Projects config YAML"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    projects = load_projects(config)
    out, count = run_scan(projects, cfg)
    print_kv("scan complete", {"output": out, "files": count, "projects": len(projects)})

