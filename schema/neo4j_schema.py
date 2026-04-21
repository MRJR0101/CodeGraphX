"""
CodeGraphX 2.0 - Neo4j Schema Setup
Phase 0.3: Database constraints, indexes, and initialization.
"""
from typing import Optional, Dict, List, Any
from neo4j import GraphDatabase


# ── Core Constraints ──────────────────────────────────────────────────────────
CONSTRAINTS = [
    "CREATE CONSTRAINT unique_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT unique_repo IF NOT EXISTS FOR (n:Repository) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT unique_package IF NOT EXISTS FOR (n:Package) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT unique_module IF NOT EXISTS FOR (n:Module) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT unique_file IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT unique_class IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT unique_function IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT unique_external IF NOT EXISTS FOR (n:ExternalSymbol) REQUIRE n.id IS UNIQUE",
]

# ── Indexes ───────────────────────────────────────────────────────────────────
INDEXES = [
    "CREATE INDEX idx_name IF NOT EXISTS FOR (n:Node) ON (n.name)",
    "CREATE INDEX idx_file_path IF NOT EXISTS FOR (n:Node) ON (n.file_path)",
    "CREATE INDEX idx_module IF NOT EXISTS FOR (n:Module) ON (n.module)",
    "CREATE INDEX idx_type IF NOT EXISTS FOR (n:Node) ON (n.type)",
    "CREATE INDEX idx_class_name IF NOT EXISTS FOR (n:Class) ON (n.name)",
    "CREATE INDEX idx_func_name IF NOT EXISTS FOR (n:Function) ON (n.name)",
]


class Neo4jConnection:
    """Manages Neo4j driver lifecycle and schema initialization."""

    def __init__(self, uri: str = "bolt://localhost:7687",
                 user: str = "neo4j", password: str = "password"):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: Any = None

    def connect(self) -> 'Neo4jConnection':
        """Establish connection to Neo4j."""
        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self._driver.verify_connectivity()
        return self

    def close(self) -> None:
        """Close the Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None

    @property
    def driver(self) -> Any:
        if not self._driver:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._driver

    def session(self, **kwargs: Any) -> Any:
        """Get a new session."""
        return self.driver.session(**kwargs)

    def initialize_schema(self) -> None:
        """Apply all constraints and indexes."""
        with self.session() as session:
            for constraint in CONSTRAINTS:
                session.run(constraint)  # type: ignore[arg-type]
            for index in INDEXES:
                session.run(index)  # type: ignore[arg-type]

    def reset_database(self) -> None:
        """Wipe all nodes and relationships. Use with caution."""
        with self.session() as session:
            session.run("MATCH (n) DETACH DELETE n")  # type: ignore[arg-type]

    def execute_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a read-only query."""
        with self.session() as session:
            result = session.run(query, parameters or {})  # type: ignore[arg-type]
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a write query."""
        with self.session() as session:
            result = session.run(query, parameters or {})  # type: ignore[arg-type]
            return result.consume()

    def __enter__(self) -> 'Neo4jConnection':
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
