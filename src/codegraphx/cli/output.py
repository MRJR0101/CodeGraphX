from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table


console = Console()


def print_kv(title: str, values: dict[str, Any]) -> None:
    table = Table(title=title)
    table.add_column("Key")
    table.add_column("Value")
    for key, value in values.items():
        table.add_row(key, str(value))
    console.print(table)


def print_rows(title: str, rows: list[dict[str, Any]], limit: int = 20) -> None:
    if not rows:
        console.print(f"[yellow]{title}: no rows[/yellow]")
        return
    keys = sorted({k for row in rows[:limit] for k in row.keys()})
    table = Table(title=title)
    for key in keys:
        table.add_column(key)
    for row in rows[:limit]:
        table.add_row(*[json.dumps(row.get(k), ensure_ascii=False) if isinstance(row.get(k), (dict, list)) else str(row.get(k, "")) for k in keys])
    console.print(table)

