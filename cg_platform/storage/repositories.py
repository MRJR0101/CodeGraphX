"""
Repository interfaces for platform persistence.
"""
from typing import List, Optional, Protocol

from ..contracts import IngestionRecord


class IngestionRepository(Protocol):
    def add(self, record: IngestionRecord) -> None:
        ...

    def update(self, record: IngestionRecord) -> None:
        ...

    def get(self, ingestion_id: str) -> Optional[IngestionRecord]:
        ...

    def list_all(self) -> List[IngestionRecord]:
        ...
