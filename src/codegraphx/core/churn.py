"""Git churn metrics and churn-aware hotspot scoring.

Churn is computed by shelling out to ``git log --numstat`` per project root.
We intentionally avoid any git library dependency: the Windows dev boxes that
run this tool already have git on PATH, and shelling out keeps this module
self-contained and unit-testable via injection.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class FileChurn:
    rel_path: str
    commits: int
    added: int
    removed: int

    @property
    def total_lines(self) -> int:
        return self.added + self.removed


@dataclass
class ChurnReport:
    project: str
    root: str
    since: str
    files: dict[str, FileChurn] = field(default_factory=dict)

    def to_rows(self) -> list[dict[str, object]]:
        return [
            {
                "project": self.project,
                "rel_path": fc.rel_path,
                "commits": fc.commits,
                "added": fc.added,
                "removed": fc.removed,
                "total_lines": fc.total_lines,
            }
            for fc in self.files.values()
        ]


GitRunner = Callable[[list[str], Path], str]


def _default_git_runner(args: list[str], cwd: Path) -> str:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git executable not found on PATH")
    completed = subprocess.run(
        [git, *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {completed.stderr.strip()}"
        )
    return completed.stdout


def parse_numstat(output: str) -> dict[str, FileChurn]:
    """Parse the output of ``git log --numstat --pretty=format:COMMIT``.

    Lines beginning with the literal sentinel ``COMMIT`` mark a new commit;
    every following non-empty line is ``added\tremoved\tpath``. Binary files
    show a dash in the numeric columns, which we treat as zero.
    """
    churn: dict[str, FileChurn] = {}
    per_file_commits: dict[str, int] = {}
    per_file_added: dict[str, int] = {}
    per_file_removed: dict[str, int] = {}

    current_commit_paths: set[str] = set()
    seen_any_commit = False

    for raw in output.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line == "COMMIT":
            # Finalize the previous commit's per-file commit counts before
            # moving on.
            for path in current_commit_paths:
                per_file_commits[path] = per_file_commits.get(path, 0) + 1
            current_commit_paths = set()
            seen_any_commit = True
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, removed_raw, path = parts[0], parts[1], parts[2]
        added = 0 if added_raw == "-" else _safe_int(added_raw)
        removed = 0 if removed_raw == "-" else _safe_int(removed_raw)
        path = path.replace("\\", "/")
        per_file_added[path] = per_file_added.get(path, 0) + added
        per_file_removed[path] = per_file_removed.get(path, 0) + removed
        current_commit_paths.add(path)

    # Finalize the trailing commit (no subsequent COMMIT line).
    if seen_any_commit:
        for path in current_commit_paths:
            per_file_commits[path] = per_file_commits.get(path, 0) + 1

    all_paths = set(per_file_added) | set(per_file_removed) | set(per_file_commits)
    for path in all_paths:
        churn[path] = FileChurn(
            rel_path=path,
            commits=per_file_commits.get(path, 0),
            added=per_file_added.get(path, 0),
            removed=per_file_removed.get(path, 0),
        )
    return churn


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def compute_churn(
    project: str,
    root: Path,
    since: str = "6.months",
    runner: GitRunner | None = None,
) -> ChurnReport:
    """Run git log --numstat in ``root`` and return a ChurnReport.

    ``since`` is any value git accepts (e.g. ``6.months``, ``2024-01-01``).
    """
    run = runner or _default_git_runner
    args = [
        "log",
        f"--since={since.replace('.', ' ')}",
        "--numstat",
        "--pretty=format:COMMIT",
    ]
    try:
        output = run(args, root)
    except RuntimeError:
        # Not a git repo or git missing: return an empty report so callers
        # can still produce a ranking based on graph coupling alone.
        return ChurnReport(project=project, root=str(root), since=since, files={})
    files = parse_numstat(output)
    return ChurnReport(project=project, root=str(root), since=since, files=files)


def churn_weight(file_churn: FileChurn | None) -> float:
    """Return a churn multiplier in the range [1.0, ~6.0].

    Uses ``log1p`` so a handful of small commits barely budges the score but
    a heavily-churned file is weighted noticeably higher.
    """
    if file_churn is None:
        return 1.0
    return 1.0 + math.log1p(file_churn.total_lines) + 0.5 * math.log1p(file_churn.commits)


@dataclass(frozen=True)
class HotspotRow:
    project: str
    rel_path: str
    functions: int
    edges: int
    churn_commits: int
    churn_lines: int
    base_score: float
    weight: float
    score: float


def rank_hotspots(
    file_stats: Iterable[dict[str, object]],
    churn_by_project: dict[str, ChurnReport],
    top_n: int = 25,
) -> list[HotspotRow]:
    """Combine graph-derived per-file stats with churn to produce a ranking.

    ``file_stats`` items must contain keys: project, rel_path, functions, edges.
    ``edges`` can be any coupling proxy such as fan_in+fan_out or imports count.
    """
    rows: list[HotspotRow] = []
    for stat in file_stats:
        project = str(stat.get("project", ""))
        rel_path = str(stat.get("rel_path", ""))
        functions_raw = stat.get("functions", 0) or 0
        edges_raw = stat.get("edges", 0) or 0
        functions = int(functions_raw) if isinstance(functions_raw, (int, float, str)) else 0
        edges = int(edges_raw) if isinstance(edges_raw, (int, float, str)) else 0
        report = churn_by_project.get(project)
        file_churn = report.files.get(rel_path) if report else None
        base = 1.0 + functions + edges
        weight = churn_weight(file_churn)
        score = base * weight
        rows.append(
            HotspotRow(
                project=project,
                rel_path=rel_path,
                functions=functions,
                edges=edges,
                churn_commits=file_churn.commits if file_churn else 0,
                churn_lines=file_churn.total_lines if file_churn else 0,
                base_score=round(base, 4),
                weight=round(weight, 4),
                score=round(score, 4),
            )
        )
    rows.sort(key=lambda row: row.score, reverse=True)
    return rows[:top_n]


def file_stats_from_events(events: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Derive per-file function and edge counts from an events stream.

    We count ``Function`` nodes per ``file_uid`` and any edge whose ``src_uid``
    starts with the file_uid as "edges". The file's ``rel_path`` comes from
    the ``File`` node. Files without a File node are skipped.
    """
    file_props: dict[str, dict[str, object]] = {}
    func_counts: dict[str, int] = {}
    edge_counts: dict[str, int] = {}

    for event in events:
        kind = event.get("kind")
        if kind == "node":
            label = event.get("label")
            uid = str(event.get("uid", ""))
            props = event.get("props")
            if not isinstance(props, dict):
                props = {}
            if label == "File":
                file_props[uid] = props
            elif label == "Function":
                file_uid = str(props.get("file_uid", ""))
                if file_uid:
                    func_counts[file_uid] = func_counts.get(file_uid, 0) + 1
        elif kind == "edge":
            src_uid = str(event.get("src_uid", ""))
            # src_uid for a File-rooted edge IS the file_uid.
            # src_uid for a Function-rooted edge is "<file_uid>:<fn>:<line>".
            # Strip the suffix so both contribute to the same file bucket.
            file_uid = src_uid
            if ":" in src_uid:
                parts = src_uid.split(":")
                # File uids look like "<project>:<rel_path>" so len == 2.
                # Function uids look like "<project>:<rel_path>:<name>:<line>".
                if len(parts) >= 4:
                    file_uid = ":".join(parts[:2])
                elif len(parts) >= 2:
                    file_uid = ":".join(parts[:2])
            if file_uid in file_props:
                edge_counts[file_uid] = edge_counts.get(file_uid, 0) + 1

    rows: list[dict[str, object]] = []
    for file_uid, props in file_props.items():
        rows.append(
            {
                "project": props.get("project", ""),
                "rel_path": props.get("rel_path", ""),
                "functions": func_counts.get(file_uid, 0),
                "edges": edge_counts.get(file_uid, 0),
            }
        )
    return rows
