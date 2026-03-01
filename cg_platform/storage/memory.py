"""
In-memory repositories for local development and tests.
"""
from threading import Lock
from typing import Dict, List, Optional

from ..contracts import IngestionRecord
from .repositories import IngestionRepository


class InMemoryIngestionRepository(IngestionRepository):
    def __init__(self):
        self._records: Dict[str, IngestionRecord] = {}
        self._lock = Lock()

    def add(self, record: IngestionRecord) -> None:
        with self._lock:
            self._records[record.id] = record

    def update(self, record: IngestionRecord) -> None:
        with self._lock:
            self._records[record.id] = record

    def get(self, ingestion_id: str) -> Optional[IngestionRecord]:
        with self._lock:
            return self._records.get(ingestion_id)

    def list_all(self) -> List[IngestionRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)
