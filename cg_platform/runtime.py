"""
Dependency assembly for platform scaffold.
"""
from dataclasses import dataclass

try:
    from codegraphx.core.pipeline import IngestionPipeline
except ModuleNotFoundError:
    from core.pipeline import IngestionPipeline
from .policy.gates import QualityPolicy
from .services import PipelineIngestionService, GraphQueryService
from .storage.memory import InMemoryIngestionRepository


@dataclass
class RuntimeContainer:
    ingestion_repository: InMemoryIngestionRepository
    ingestion_service: PipelineIngestionService
    query_service: GraphQueryService
    quality_policy: QualityPolicy


def build_runtime() -> RuntimeContainer:
    repository = InMemoryIngestionRepository()
    pipeline = IngestionPipeline()
    quality_policy = QualityPolicy()
    ingestion_service = PipelineIngestionService(repository=repository, pipeline=pipeline)
    query_service = GraphQueryService(pipeline=pipeline)

    return RuntimeContainer(
        ingestion_repository=repository,
        ingestion_service=ingestion_service,
        query_service=query_service,
        quality_policy=quality_policy,
    )
