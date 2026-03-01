"""
Runtime configuration for platform-facing services.
"""
from pydantic import BaseModel, Field


class PlatformApiConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    enable_docs: bool = True


class PlatformWorkerConfig(BaseModel):
    poll_interval_seconds: float = 0.5
    max_retries: int = 2


class PlatformQualityConfig(BaseModel):
    max_avg_complexity: float = 12.0
    max_risk_nodes: int = 25
    max_cyclic_nodes: int = 15


class PlatformConfig(BaseModel):
    api: PlatformApiConfig = Field(default_factory=PlatformApiConfig)
    worker: PlatformWorkerConfig = Field(default_factory=PlatformWorkerConfig)
    quality: PlatformQualityConfig = Field(default_factory=PlatformQualityConfig)


platform_config = PlatformConfig()
