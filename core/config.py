"""
CodeGraphX 2.0 - Configuration
Central configuration for all phases.
"""
from pydantic import BaseModel, Field


class Neo4jConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"


class ParserConfig(BaseModel):
    max_file_size_kb: int = 500
    supported_extensions: dict = Field(default_factory=lambda: {
        "python": [".py"],
        "javascript": [".js", ".jsx", ".mjs"],
    })
    exclude_dirs: list = Field(default_factory=lambda: [
        "__pycache__", "node_modules", ".git", ".venv",
        "venv", "env", ".tox", ".mypy_cache",
    ])


class MetricsConfig(BaseModel):
    god_class_threshold: int = 20       # fan_in + fan_out
    max_dependency_depth: int = 5
    high_complexity_threshold: int = 10


class SemanticConfig(BaseModel):
    model_name: str = "all-MiniLM-L6-v2"
    top_k: int = 10
    expansion_hops: int = 2
    max_body_lines: int = 20


class LLMConfig(BaseModel):
    max_result_nodes: int = 1000
    query_timeout_seconds: int = 30
    forbidden_clauses: list = Field(default_factory=lambda: [
        "CREATE", "DELETE", "MERGE", "SET", "REMOVE", "DROP",
    ])


class CodeGraphXConfig(BaseModel):
    """Master configuration."""
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


# Default singleton
config = CodeGraphXConfig()
