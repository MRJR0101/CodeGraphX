"""
CodeGraphX 2.0 - Unified Code Intelligence Platform

Layers:
  1. Code Property Graph (deep semantic structure)
  2. Architectural Knowledge Graph (module + dependency clarity)
  3. LLM Query & Semantic Retrieval Interface

Usage:
    from codegraphx import IngestionPipeline
    pipeline = IngestionPipeline()
    ctx = pipeline.ingest("/path/to/repo")
"""
__version__ = "0.2.0"

from codegraphx.core.config import CodeGraphXConfig, config
from codegraphx.core.models import IngestionContext
from codegraphx.core.pipeline import IngestionPipeline

__all__ = [
    "IngestionPipeline",
    "IngestionContext",
    "CodeGraphXConfig",
    "config",
]
