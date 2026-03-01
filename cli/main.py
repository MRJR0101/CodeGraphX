"""Legacy CLI compatibility shim.

This file exists because older docs/scripts may still call `python cli/main.py`.
It forwards to the canonical Typer CLI under `src/codegraphx`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "src"
    if src.exists():
        sys.path.insert(0, str(src))


def main() -> int:
    _ensure_src_on_path()
    repo_root = Path(__file__).resolve().parents[1]

    # Keep `python cli/main.py --version` lightweight for first-run diagnostics.
    if "--version" in sys.argv:
        init_file = repo_root / "src" / "codegraphx" / "__init__.py"
        namespace: dict[str, object] = {}
        exec(init_file.read_text(encoding="utf-8"), namespace)
        print(namespace.get("__version__", "unknown"))
        return 0

    try:
        from codegraphx.__main__ import main as package_main
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown module"
        print(
            "CodeGraphX dependencies are not installed for this interpreter.\n"
            "Run `python -m pip install -e .` from the repository root, then use\n"
            "`python -m codegraphx --help` or `codegraphx --help`.\n"
            f"Missing module: {missing}",
            file=sys.stderr,
        )
        return 1

    return int(package_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
