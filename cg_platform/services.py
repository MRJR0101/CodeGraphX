"""
Default service implementations for platform scaffold.
"""
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional

try:
    from codegraphx.core.models import generate_id
    from codegraphx.core.pipeline import IngestionPipeline
    from codegraphx.llm.query_interface import QueryValidator
except ModuleNotFoundError:
    from core.models import generate_id
    from core.pipeline import IngestionPipeline
    from llm.query_interface import QueryValidator
from .contracts import (
    IngestionRequest,
    IngestionRecord,
    IngestionService,
    IngestionStatus,
    SemanticQueryRequest,
    CypherValidationRequest,
    CypherValidationResult,
    QueryService,
)
from .policy.gates import QualityPolicy
from .storage.repositories import IngestionRepository


class PipelineIngestionService(IngestionService):
    def __init__(self, repository: IngestionRepository, pipeline: Optional[IngestionPipeline] = None):
        self.repository = repository
        self.pipeline = pipeline or IngestionPipeline()
        self.quality = QualityPolicy()

    def ingest(self, request: IngestionRequest) -> IngestionRecord:
        record = IngestionRecord(
            id=generate_id(),
            status=IngestionStatus.running,
        )
        self.repository.add(record)

        try:
            ctx = self.pipeline.ingest(
                repo_path=request.repo_path,
                language=request.language,
                write_to_neo4j=request.write_to_neo4j,
                skip_semantic=request.skip_semantic,
            )
            metrics_summary = self.pipeline.get_metrics_summary()
            gate_result = self.quality.evaluate(metrics_summary)

            record.status = IngestionStatus.succeeded
            record.completed_at = datetime.now(UTC)
            record.summary = {
                "repo_id": ctx.repo_id,
                "files_parsed": len(ctx.ast_nodes),
                "arch_nodes": len(ctx.arch_nodes),
                "arch_relationships": len(ctx.arch_relationships),
                "cpg_nodes": len(ctx.cpg_nodes),
                "cpg_relationships": len(ctx.cpg_relationships),
                "errors": len(ctx.errors),
                "quality_gate_passed": gate_result.passed,
                "quality_violations": gate_result.violations,
            }
            self.repository.update(record)
            return record
        except Exception as exc:
            record.status = IngestionStatus.failed
            record.completed_at = datetime.now(UTC)
            record.error = str(exc)
            self.repository.update(record)
            return record

    def get_record(self, ingestion_id: str) -> Optional[IngestionRecord]:
        return self.repository.get(ingestion_id)

    def list_records(self) -> List[IngestionRecord]:
        return self.repository.list_all()


class GraphQueryService(QueryService):
    def __init__(self, pipeline: IngestionPipeline):
        self.pipeline = pipeline
        self.validator = QueryValidator()

    def semantic_query(self, request: SemanticQueryRequest) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if request.top_k:
            kwargs["top_k"] = request.top_k
        return self.pipeline.semantic_query(request.question, **kwargs)

    def validate_cypher(self, request: CypherValidationRequest) -> CypherValidationResult:
        result = self.validator.validate(request.query)
        return CypherValidationResult(
            valid=result["valid"],
            errors=result["errors"],
            cleaned=result["cleaned"],
        )
