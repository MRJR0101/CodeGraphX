from __future__ import annotations

import sys

import typer

from codegraphx import __version__
from codegraphx.cli.completions import render_completion_script
from codegraphx.cli.commands import (
    analyze,
    ask,
    compare,
    delta,
    doctor,
    enrich,
    extract,
    impact,
    load,
    parse,
    pipeline,
    query,
    scan,
    search,
    snapshots,
)


app = typer.Typer(help="CodeGraphX CLI", invoke_without_command=True)


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Show version and exit", is_eager=True),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


app.command("scan")(scan.command)
app.command("parse")(parse.command)
app.command("extract")(extract.command)
app.command("load")(load.command)
app.command("query")(query.command)
app.command("search")(search.command)
app.command("ask")(ask.command)
app.command("compare")(compare.command)
app.command("doctor")(doctor.command)
app.command("impact")(impact.command)
app.command("delta")(delta.command)
app.add_typer(snapshots.app, name="snapshots")
app.add_typer(analyze.app, name="analyze")
app.add_typer(enrich.app, name="enrich")
app.add_typer(pipeline.app, name="pipeline")


@app.command("completions")
def completions(
    shell: str = typer.Argument(..., help="powershell|bash|zsh|fish"),
) -> None:
    """Print a shell completion script for the requested shell.

    For PowerShell, redirect the output into your $PROFILE or a file sourced
    from it, e.g.::

        codegraphx completions powershell | Out-File -Encoding utf8 $PROFILE
    """
    script = render_completion_script(shell, app_name="codegraphx", commands=_top_level_commands())
    typer.echo(script)


def _top_level_commands() -> list[str]:
    """Return the list of registered top-level Typer command names."""
    names: list[str] = []
    for command_info in app.registered_commands:
        name = command_info.name or (command_info.callback.__name__ if command_info.callback else "")
        if name and name not in names:
            names.append(name)
    for group_info in app.registered_groups:
        name = group_info.name or ""
        if name and name not in names:
            names.append(name)
    return sorted(names)


if __name__ == "__main__":
    sys.exit(app())
