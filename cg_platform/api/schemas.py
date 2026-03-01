"""
API request/response schemas.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..contracts import IngestionStatus


class IngestionCreateRequest(BaseModel):
    repo_path: str
    language: str = "python"
    write_to_neo4j: bool = False
    skip_semantic: bool = False


class IngestionRecordResponse(BaseModel):
    id: str
    status: IngestionStatus
    summary: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class SemanticQueryApiRequest(BaseModel):
    question: str
    top_k: Optional[int] = None


class SemanticQueryApiResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(default_factory=list)


class CypherValidateApiRequest(BaseModel):
    query: str


class CypherValidateApiResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    cleaned: str = ""
