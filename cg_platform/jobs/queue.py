"""
Simple job queue scaffold (replace with Redis/SQS/Kafka in production).
"""
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any, Dict, Optional

try:
    from codegraphx.core.models import generate_id
except ModuleNotFoundError:
    from core.models import generate_id


@dataclass
class Job:
    job_type: str
    payload: Dict[str, Any]
    id: str = field(default_factory=generate_id)


class InMemoryJobQueue:
    def __init__(self):
        self._queue: Queue[Job] = Queue()

    def publish(self, job_type: str, payload: Dict[str, Any]) -> Job:
        job = Job(job_type=job_type, payload=payload)
        self._queue.put(job)
        return job

    def consume(self, timeout_seconds: float = 0.1) -> Optional[Job]:
        try:
            return self._queue.get(timeout=timeout_seconds)
        except Empty:
            return None

    def ack(self) -> None:
        self._queue.task_done()
