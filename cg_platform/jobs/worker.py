"""
Worker scaffold for asynchronous ingestion.
"""
import time

from ..config import platform_config
from ..contracts import IngestionRequest
from .queue import InMemoryJobQueue
from ..services import PipelineIngestionService


class IngestionWorker:
    def __init__(self, queue: InMemoryJobQueue, service: PipelineIngestionService):
        self.queue = queue
        self.service = service
        self.running = False

    def run_once(self) -> bool:
        job = self.queue.consume(timeout_seconds=platform_config.worker.poll_interval_seconds)
        if not job:
            return False

        if job.job_type == "ingest":
            request = IngestionRequest(**job.payload)
            self.service.ingest(request)

        self.queue.ack()
        return True

    def run_forever(self) -> None:
        self.running = True
        while self.running:
            processed = self.run_once()
            if not processed:
                time.sleep(platform_config.worker.poll_interval_seconds)

    def stop(self) -> None:
        self.running = False
