"""
CodeGraphX platform scaffold.

This package adds production-facing structure around the existing analysis core:
- contracts (service interfaces and request/response models)
- storage (repository interfaces + in-memory implementation)
- services (pipeline and query service implementations)
- policy (quality gates)
- jobs (queue and worker scaffolding)
- api (FastAPI app factory and routes)
"""

from .runtime import RuntimeContainer, build_runtime

__all__ = [
    "RuntimeContainer",
    "build_runtime",
]
