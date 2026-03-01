"""Legacy setuptools shim for tools that still invoke setup.py directly.

Primary packaging is configured in pyproject.toml with hatchling.
"""

from setuptools import find_packages, setup

setup(
    name="codegraphx",
    version="0.2.0",
    description="Multi-layer static analysis and semantic code intelligence system",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "click",
        "fastapi",
        "neo4j",
        "numpy",
        "pydantic",
        "pytest",
        "sentence_transformers",
        "setuptools",
        "tree_sitter",
        "tree_sitter_javascript",
        "tree_sitter_python",
        "uvicorn",
    ],
    entry_points={
        "console_scripts": [
            "codegraphx=codegraphx.__main__:main",
        ],
    },
)
