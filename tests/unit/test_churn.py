from __future__ import annotations

from pathlib import Path

from codegraphx.core.churn import (
    ChurnReport,
    FileChurn,
    churn_weight,
    compute_churn,
    file_stats_from_events,
    parse_numstat,
    rank_hotspots,
)

NUMSTAT_SAMPLE = """COMMIT
10\t2\tsrc/a.py
3\t1\tsrc/b.py
COMMIT
5\t0\tsrc/a.py
-\t-\tdocs/logo.png
COMMIT
0\t4\tsrc/b.py
"""


def test_parse_numstat_counts_commits_and_lines() -> None:
    churn = parse_numstat(NUMSTAT_SAMPLE)
    assert set(churn.keys()) == {"src/a.py", "src/b.py", "docs/logo.png"}
    assert churn["src/a.py"] == FileChurn("src/a.py", commits=2, added=15, removed=2)
    assert churn["src/b.py"] == FileChurn("src/b.py", commits=2, added=3, removed=5)
    binary = churn["docs/logo.png"]
    assert binary.added == 0 and binary.removed == 0 and binary.commits == 1


def test_churn_weight_monotonic() -> None:
    low = FileChurn("a", commits=1, added=2, removed=1)
    high = FileChurn("b", commits=50, added=1000, removed=500)
    assert churn_weight(None) == 1.0
    assert churn_weight(low) < churn_weight(high)
    assert churn_weight(high) > 2.0


def test_compute_churn_injected_runner() -> None:
    def fake_runner(_args: list[str], _cwd: Path) -> str:
        return NUMSTAT_SAMPLE

    report = compute_churn("demo", Path("."), since="1.month", runner=fake_runner)
    assert report.project == "demo"
    assert "src/a.py" in report.files
    rows = report.to_rows()
    assert any(r["rel_path"] == "src/a.py" for r in rows)


def test_compute_churn_handles_git_failure() -> None:
    def failing_runner(_args: list[str], _cwd: Path) -> str:
        raise RuntimeError("not a git repo")

    report = compute_churn("demo", Path("."), runner=failing_runner)
    assert report.files == {}


def test_rank_hotspots_weights_by_churn() -> None:
    stats = [
        {"project": "demo", "rel_path": "src/a.py", "functions": 3, "edges": 5},
        {"project": "demo", "rel_path": "src/b.py", "functions": 3, "edges": 5},
    ]
    report = ChurnReport(
        project="demo",
        root=".",
        since="6.months",
        files={
            "src/a.py": FileChurn("src/a.py", commits=20, added=800, removed=400),
            "src/b.py": FileChurn("src/b.py", commits=1, added=2, removed=1),
        },
    )
    ranked = rank_hotspots(stats, {"demo": report}, top_n=5)
    assert ranked[0].rel_path == "src/a.py"
    assert ranked[0].score > ranked[1].score
    assert ranked[0].churn_commits == 20


def test_file_stats_from_events() -> None:
    events = [
        {"kind": "node", "label": "File", "uid": "demo:src/a.py", "props": {"project": "demo", "rel_path": "src/a.py"}},
        {
            "kind": "node",
            "label": "Function",
            "uid": "demo:src/a.py:foo:1",
            "props": {"file_uid": "demo:src/a.py", "name": "foo"},
        },
        {
            "kind": "node",
            "label": "Function",
            "uid": "demo:src/a.py:bar:5",
            "props": {"file_uid": "demo:src/a.py", "name": "bar"},
        },
        {"kind": "edge", "type": "CALLS", "src_uid": "demo:src/a.py", "dst_uid": "symbol:print"},
        {"kind": "edge", "type": "CALLS", "src_uid": "demo:src/a.py:foo:1", "dst_uid": "symbol:bar"},
    ]
    stats = file_stats_from_events(events)
    assert len(stats) == 1
    row = stats[0]
    assert row["rel_path"] == "src/a.py"
    assert row["functions"] == 2
    assert row["edges"] == 2
