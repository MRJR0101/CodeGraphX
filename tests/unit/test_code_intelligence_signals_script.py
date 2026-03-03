from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "code_intelligence_signals.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("code_intelligence_signals_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyze_scan_extracts_calls_complexity_and_similarity(tmp_path: Path) -> None:
    mod = _load_script_module()
    project_root = tmp_path / "repo"
    project_root.mkdir()

    file_a = project_root / "a.py"
    file_b = project_root / "b.py"

    file_a.write_text(
        "\n".join(
            [
                "import os",
                "",
                "def bar(y):",
                "    return y + 1",
                "",
                "def foo(x):",
                "    if x > 0:",
                "        return bar(x)",
                "    return 0",
                "",
                "def dup(v):",
                "    if v:",
                "        return v",
                "    return 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    file_b.write_text(
        "\n".join(
            [
                "import a",
                "",
                "def dup(v):",
                "    if v:",
                "        return v",
                "    return 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scan = tmp_path / "scan.jsonl"
    scan.write_text(
        "\n".join(
            [
                json.dumps({"path": str(file_a), "ext": ".py"}),
                json.dumps({"path": str(file_b), "ext": ".py"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    results = mod.analyze_scan(
        source_path=str(project_root),
        scan_artifact=scan,
        min_file_similarity=0.1,
        min_function_similarity=0.1,
        max_file_pairs=50,
        max_function_pairs=50,
        complexity_threshold=2,
        exclude_subpaths=[],
        use_default_excludes=False,
    )

    summary = results["summary"]
    assert summary["files_analyzed"] == 2
    assert summary["functions_analyzed"] >= 4
    assert summary["call_edges"] >= 1
    assert summary["max_cyclomatic"] >= 2

    internal_calls = [row for row in results["calls"] if row["callee_name"] == "bar" and row["is_internal"] == 1]
    assert internal_calls

    exact_dup = [row for row in results["function_pairs"] if row["similarity"] == 1.0]
    assert exact_dup


def test_analyze_scan_js_uses_function_scope_not_whole_file(tmp_path: Path) -> None:
    mod = _load_script_module()
    project_root = tmp_path / "repo"
    project_root.mkdir()

    file_js = project_root / "mod.js"
    file_js.write_text(
        "\n".join(
            [
                "function alpha(x) {",
                "  if (x > 2 && x < 9) {",
                "    return beta(x);",
                "  }",
                "  return x;",
                "}",
                "",
                "const beta = (y) => {",
                "  for (let i = 0; i < y; i++) {",
                "    helper(i);",
                "  }",
                "  return y;",
                "};",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scan = tmp_path / "scan.jsonl"
    scan.write_text(json.dumps({"path": str(file_js), "ext": ".js"}) + "\n", encoding="utf-8")

    results = mod.analyze_scan(
        source_path=str(project_root),
        scan_artifact=scan,
        min_file_similarity=0.1,
        min_function_similarity=0.1,
        max_file_pairs=50,
        max_function_pairs=50,
        complexity_threshold=2,
        exclude_subpaths=[],
        use_default_excludes=False,
    )

    functions = [row for row in results["complexity"] if row["file_path"] == str(file_js)]
    names = {row["function_name"] for row in functions}
    assert "alpha" in names
    assert "beta" in names

    alpha = next(row for row in functions if row["function_name"] == "alpha")
    beta = next(row for row in functions if row["function_name"] == "beta")
    assert alpha["cyclomatic"] < 20
    assert beta["cyclomatic"] < 20

    callee_names = {row["callee_name"] for row in results["calls"]}
    assert "beta" in callee_names
    assert "helper" in callee_names


def test_persist_results_writes_tables(tmp_path: Path) -> None:
    mod = _load_script_module()
    conn = sqlite3.connect(":memory:")

    results = {
        "summary": {
            "files_analyzed": 2,
            "functions_analyzed": 3,
            "dependency_edges": 2,
            "call_edges": 1,
            "internal_call_edges": 1,
            "avg_cyclomatic": 2.0,
            "max_cyclomatic": 3,
            "p95_cyclomatic": 3.0,
            "high_complexity_functions": 1,
            "file_similarity_pairs": 1,
            "function_similarity_pairs": 1,
            "max_call_chain_depth": 2,
            "scan_rows": 2,
            "missing_files": 0,
            "skipped_by_filter": 0,
        },
        "dependencies": [
            {"file_path": r"c:\x\a.py", "import_name": "os", "is_internal": 0, "import_count": 1},
        ],
        "calls": [
            {
                "caller_uid": "a.py::foo:1",
                "caller_file": r"c:\x\a.py",
                "callee_name": "bar",
                "is_internal": 1,
                "callee_uid": "a.py::bar:5",
                "call_count": 2,
            }
        ],
        "complexity": [
            {
                "file_path": r"c:\x\a.py",
                "function_uid": "a.py::foo:1",
                "function_name": "foo",
                "start_line": 1,
                "end_line": 5,
                "language": "python",
                "cyclomatic": 3,
                "call_count": 2,
            }
        ],
        "file_pairs": [
            {
                "left_id": r"c:\x\a.py",
                "right_id": r"c:\x\b.py",
                "similarity": 0.9,
                "evidence": {"mode": "token_jaccard"},
            },
        ],
        "function_pairs": [
            {
                "left_id": "a.py::foo:1",
                "right_id": "b.py::foo:1",
                "similarity": 0.95,
                "evidence": {"mode": "token_jaccard"},
            }
        ],
    }

    mod.persist_results(
        conn,
        source_path=r"c:\x",
        source_project="x",
        scan_artifact=tmp_path / "scan.jsonl",
        results=results,
        replace_existing=True,
    )

    cur = conn.cursor()
    assert cur.execute("SELECT COUNT(*) FROM codegraphx_project_intelligence").fetchone()[0] == 1
    assert cur.execute("SELECT COUNT(*) FROM codegraphx_dependency_edges").fetchone()[0] == 1
    assert cur.execute("SELECT COUNT(*) FROM codegraphx_call_edges").fetchone()[0] == 1
    assert cur.execute("SELECT COUNT(*) FROM codegraphx_complexity_nodes").fetchone()[0] == 1
    assert cur.execute("SELECT COUNT(*) FROM codegraphx_similarity_pairs").fetchone()[0] == 2
    conn.close()
