from __future__ import annotations

import sys

import typer
from typer.main import get_command

from codegraphx import __version__
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


@app.command("completions")
def completions(shell: str = typer.Argument(..., help="bash|zsh|fish|powershell")) -> None:
    cmd = get_command(app)
    typer.echo(cmd.get_help(typer.Context(cmd)))
    typer.echo("")
    typer.echo(f"Completion generation hint: use your shell tooling for '{shell}'.")


if __name__ == "__main__":
    sys.exit(app())
