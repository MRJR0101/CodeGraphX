from __future__ import annotations

import typer

from codegraphx.cli.output import print_kv
from codegraphx.core.config import load_settings
from codegraphx.core.stages import run_parse


def command(
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
) -> None:
    cfg = load_settings(settings)
    out, count = run_parse(cfg)
    print_kv("parse complete", {"output": out, "records": count})

