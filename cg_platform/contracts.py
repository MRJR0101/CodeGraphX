"""
Platform contracts and transport-safe models.
"""
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field


class IngestionStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class IngestionRequest(BaseModel):
    repo_path: str
    language: str = "python"
    write_to_neo4j: bool = False
    skip_semantic: bool = False


class IngestionRecord(BaseModel):
    id: str
    status: IngestionStatus = IngestionStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)


class SemanticQueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = None


class CypherValidationRequest(BaseModel):
    query: str


class CypherValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    cleaned: str = ""


class QualityGateResult(BaseModel):
    passed: bool
    violations: List[str] = Field(default_factory=list)
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)


class IngestionService(Protocol):
    def ingest(self, request: IngestionRequest) -> IngestionRecord:
        ...

    def get_record(self, ingestion_id: str) -> Optional[IngestionRecord]:
        ...

    def list_records(self) -> List[IngestionRecord]:
        ...


class QueryService(Protocol):
    def semantic_query(self, request: SemanticQueryRequest) -> List[Dict[str, Any]]:
        ...

    def validate_cypher(self, request: CypherValidationRequest) -> CypherValidationResult:
        ...

