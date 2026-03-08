from __future__ import annotations

from pathlib import Path

from codegraphx.core.config import load_settings


def test_load_settings_reads_dotenv_from_config_parent(tmp_path: Path, monkeypatch: object) -> None:
    repo_root = tmp_path / "repo"
    config_dir = repo_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_yaml = config_dir / "default.yaml"
    dotenv_path = repo_root / ".env"

    settings_yaml.write_text(
        "\n".join(
            [
                "run:",
                "  out_dir: data",
                "  max_files: 0",
                "  include_ext: ['.py']",
                "neo4j:",
                "  uri: ${NEO4J_URI:-bolt://localhost:7687}",
                "  user: ${NEO4J_USER:-neo4j}",
                "  password: ${NEO4J_PASSWORD:-}",
                "  database: ${NEO4J_DATABASE:-neo4j}",
                "meilisearch:",
                "  enabled: false",
                "  host: localhost",
                "  port: 7700",
                "  index: codegraphx",
            ]
        ),
        encoding="utf-8",
    )
    dotenv_path.write_text("NEO4J_PASSWORD=from-dotenv\n", encoding="utf-8")

    settings = load_settings(settings_yaml)
    expected_password = dotenv_path.read_text(encoding="utf-8").strip().split("=", 1)[1]

    assert settings.neo4j_password == expected_password
