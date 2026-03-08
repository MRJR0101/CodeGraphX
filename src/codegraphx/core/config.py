from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
import yaml  # type: ignore[import-untyped]


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+):-([^}]*)\}")
_LOADED_DOTENV_PATHS: set[Path] = set()
_DOTENV_MANAGED_KEYS: dict[str, Path] = {}


@dataclass(frozen=True)
class Project:
    name: str
    root: Path
    exclude: list[str]


@dataclass(frozen=True)
class RuntimeSettings:
    out_dir: Path
    include_ext: list[str]
    max_files: int
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    meilisearch_enabled: bool
    meilisearch_host: str
    meilisearch_port: int
    meilisearch_index: str


def _expand_env_tokens(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2)
        return os.environ.get(key, default)

    return ENV_PATTERN.sub(repl, text)


def _load_env_files(anchor_path: Path) -> None:
    candidates: list[Path] = [Path.cwd() / ".env"]
    resolved = anchor_path.resolve()
    candidates.extend(parent / ".env" for parent in (resolved.parent, *resolved.parents))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if not candidate.exists() or candidate in _LOADED_DOTENV_PATHS:
            continue
        values = dotenv_values(candidate)
        for key, value in values.items():
            if value is None:
                continue
            current_source = _DOTENV_MANAGED_KEYS.get(key)
            if key not in os.environ or current_source is not None:
                os.environ[key] = value
                _DOTENV_MANAGED_KEYS[key] = candidate
        _LOADED_DOTENV_PATHS.add(candidate)


def load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    _load_env_files(config_path)
    raw = config_path.read_text(encoding="utf-8")
    expanded = _expand_env_tokens(raw)
    loaded = yaml.safe_load(expanded) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {path}")
    return loaded


def load_projects(config_path: str | Path) -> list[Project]:
    data = load_yaml(config_path)
    raw_projects = data.get("projects", [])
    if not isinstance(raw_projects, list):
        raise ValueError("projects config must contain a list under 'projects'")

    projects: list[Project] = []
    for entry in raw_projects:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        root = str(entry.get("root", "")).strip()
        exclude = entry.get("exclude", [])
        if not name or not root:
            continue
        if not isinstance(exclude, list):
            exclude = []
        projects.append(Project(name=name, root=Path(root), exclude=[str(x) for x in exclude]))
    return projects


def load_settings(settings_path: str | Path) -> RuntimeSettings:
    data = load_yaml(settings_path)
    run = data.get("run", {})
    neo4j = data.get("neo4j", {})
    meili = data.get("meilisearch", {})

    include_ext = run.get("include_ext", [".py", ".js", ".ts"])
    if not isinstance(include_ext, list):
        include_ext = [".py", ".js", ".ts"]
    include_ext = [str(x).lower() for x in include_ext]

    return RuntimeSettings(
        out_dir=Path(str(run.get("out_dir", "data"))),
        include_ext=include_ext,
        max_files=int(run.get("max_files", 0) or 0),
        neo4j_uri=str(neo4j.get("uri", "bolt://localhost:7687")),
        neo4j_user=str(neo4j.get("user", "neo4j")),
        neo4j_password=str(neo4j.get("password", "")),
        neo4j_database=str(neo4j.get("database", "neo4j")),
        meilisearch_enabled=bool(meili.get("enabled", False)),
        meilisearch_host=str(meili.get("host", "localhost")),
        meilisearch_port=int(meili.get("port", 7700)),
        meilisearch_index=str(meili.get("index", "codegraphx")),
    )
