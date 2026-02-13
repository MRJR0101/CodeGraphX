from __future__ import annotations

import importlib.util
from pathlib import Path

import typer

from codegraphx.cli.output import print_rows
from codegraphx.core.config import load_projects, load_settings
from codegraphx.graph.neo4j_client import check_connection


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def command(
    config: str = typer.Option("config/projects.yaml", help="Projects config YAML"),
    settings: str = typer.Option("config/default.yaml", help="Runtime settings YAML"),
    skip_neo4j: bool = typer.Option(False, "--skip-neo4j", help="Skip Neo4j connectivity check"),
) -> None:
    checks: list[dict[str, str]] = []

    config_path = Path(config)
    settings_path = Path(settings)
    checks.append(
        {
            "check": "projects_config_exists",
            "status": "pass" if config_path.exists() else "fail",
            "detail": str(config_path),
        }
    )
    checks.append(
        {
            "check": "settings_exists",
            "status": "pass" if settings_path.exists() else "fail",
            "detail": str(settings_path),
        }
    )

    if config_path.exists():
        try:
            projects = load_projects(config_path)
            checks.append(
                {
                    "check": "projects_loaded",
                    "status": "pass",
                    "detail": f"{len(projects)} project entries",
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append({"check": "projects_loaded", "status": "fail", "detail": str(exc)})

    try:
        runtime = load_settings(settings_path)
        checks.append({"check": "settings_loaded", "status": "pass", "detail": str(runtime.out_dir)})
    except Exception as exc:  # noqa: BLE001
        runtime = None
        checks.append({"check": "settings_loaded", "status": "fail", "detail": str(exc)})

    for module in ("yaml", "neo4j", "typer", "rich"):
        checks.append(
            {
                "check": f"module_{module}",
                "status": "pass" if _module_available(module) else "fail",
                "detail": module,
            }
        )

    if skip_neo4j:
        checks.append({"check": "neo4j_connection", "status": "skip", "detail": "skipped by flag"})
    elif runtime is None:
        checks.append({"check": "neo4j_connection", "status": "fail", "detail": "settings not loaded"})
    else:
        ok, message = check_connection(runtime)
        checks.append({"check": "neo4j_connection", "status": "pass" if ok else "fail", "detail": message})

    print_rows("doctor checks", checks, limit=len(checks))
    failed = [c for c in checks if c["status"] == "fail"]
    if failed:
        raise typer.Exit(code=1)

