from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "chunked_scan_enrich.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("chunked_scan_enrich_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sanitize_tag() -> None:
    mod = _load_script_module()
    assert mod._sanitize_tag("00_PyToolbelt") == "00_pytoolbelt"
    assert mod._sanitize_tag("My Project / Alpha") == "my_project___alpha"
    assert mod._sanitize_tag("!!!") == "scan"


def test_chunked_partitioning() -> None:
    mod = _load_script_module()
    items = [Path(f"C:/x/{i}") for i in range(7)]
    chunks = list(mod._chunked(items, 3))
    assert len(chunks) == 3
    assert [len(c) for c in chunks] == [3, 3, 1]
    assert chunks[0][0].name == "0"
    assert chunks[-1][0].name == "6"
