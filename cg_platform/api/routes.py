"""
FastAPI route registration for platform scaffold.
"""
from fastapi import APIRouter, HTTPException

from .schemas import (
    IngestionCreateRequest,
    IngestionRecordResponse,
    SemanticQueryApiRequest,
    SemanticQueryApiResponse,
    CypherValidateApiRequest,
    CypherValidateApiResponse,
)
from ..contracts import (
    IngestionRequest,
    SemanticQueryRequest,
    CypherValidationRequest,
)
from ..runtime import RuntimeContainer


def build_router(runtime: RuntimeContainer) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @router.post("/v1/ingestions", response_model=IngestionRecordResponse)
    def create_ingestion(request: IngestionCreateRequest) -> IngestionRecordResponse:
        record = runtime.ingestion_service.ingest(
            IngestionRequest(
                repo_path=request.repo_path,
                language=request.language,
                write_to_neo4j=request.write_to_neo4j,
                skip_semantic=request.skip_semantic,
            )
        )
        return IngestionRecordResponse(
            id=record.id,
            status=record.status,
            summary=record.summary,
            error=record.error,
        )

    @router.get("/v1/ingestions/{ingestion_id}", response_model=IngestionRecordResponse)
    def get_ingestion(ingestion_id: str) -> IngestionRecordResponse:
        record = runtime.ingestion_service.get_record(ingestion_id)
        if not record:
            raise HTTPException(status_code=404, detail="Ingestion not found")
        return IngestionRecordResponse(
            id=record.id,
            status=record.status,
            summary=record.summary,
            error=record.error,
        )

    @router.get("/v1/ingestions", response_model=list[IngestionRecordResponse])
    def list_ingestions() -> list[IngestionRecordResponse]:
        records = runtime.ingestion_service.list_records()
        return [
            IngestionRecordResponse(
                id=r.id,
                status=r.status,
                summary=r.summary,
                error=r.error,
            )
            for r in records
        ]

    @router.post("/v1/queries/semantic", response_model=SemanticQueryApiResponse)
    def semantic_query(request: SemanticQueryApiRequest) -> SemanticQueryApiResponse:
        try:
            results = runtime.query_service.semantic_query(
                SemanticQueryRequest(question=request.question, top_k=request.top_k)
            )
            return SemanticQueryApiResponse(results=results)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/v1/queries/cypher/validate", response_model=CypherValidateApiResponse)
    def validate_cypher(request: CypherValidateApiRequest) -> CypherValidateApiResponse:
        result = runtime.query_service.validate_cypher(
            CypherValidationRequest(query=request.query)
        )
        return CypherValidateApiResponse(
            valid=result.valid,
            errors=result.errors,
            cleaned=result.cleaned,
        )

    return router
