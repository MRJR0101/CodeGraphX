from __future__ import annotations

import typer

from codegraphx.cli.output import print_kv
from codegraphx.core.config import load_settings
from codegraphx.core.stages import run_extract


def command(
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    relations: bool = typer.Option(True, "--relations/--no-relations", help="Extract relation edges"),
) -> None:
    cfg = load_settings(settings)
    out, count = run_extract(cfg, relations=relations)
    print_kv("extract complete", {"output": out, "events": count, "relations": relations})

