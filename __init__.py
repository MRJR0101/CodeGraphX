"""Repository-root compatibility module.

The installable package lives under ``src/codegraphx``. This file is kept
import-safe so pytest collection and repository tooling do not accidentally
execute legacy package wiring from the repository root.
"""
from __future__ import annotations

__version__ = "0.2.0"

__all__ = ["__version__"]


def __getattr__(name: str) -> object:
    raise AttributeError(
        f"{name!r} is not exported from the repository root. "
        "Import from the installed `codegraphx` package under `src/codegraphx` instead."
    )
