"""
CodeGraphX 2.0 - Unified Code Intelligence Platform
Setup configuration.
"""
from setuptools import find_packages, setup

setup(
    name="codegraphx",
    version="0.2.0",
    description="Multi-layer static analysis and semantic code intelligence system",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "tree-sitter>=0.21.0",
        "tree-sitter-python>=0.21.0",
        "tree-sitter-javascript>=0.21.0",
        "neo4j>=5.0.0",
        "numpy>=1.24.0",
        "pydantic>=2.0.0",
        "click>=8.1.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "semantic": ["sentence-transformers>=2.2.0"],
        "api": ["fastapi>=0.100.0", "uvicorn>=0.23.0"],
    },
    entry_points={
        "console_scripts": [
            "codegraphx=codegraphx.cli.main:main",
        ],
    },
)
