"""
FastAPI app factory.
"""
from typing import Optional

from fastapi import FastAPI

from ..runtime import RuntimeContainer, build_runtime
from .routes import build_router


def create_app(runtime: Optional[RuntimeContainer] = None) -> FastAPI:
    container = runtime or build_runtime()
    app = FastAPI(title="CodeGraphX Platform API", version="0.2.0")
    app.include_router(build_router(container))
    return app
