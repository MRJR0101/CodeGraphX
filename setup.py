"""Legacy setuptools shim for tools that still invoke setup.py directly.

Primary packaging is configured in pyproject.toml with hatchling.
"""

from setuptools import find_packages, setup

setup(
    name="codegraphx",
    version="0.2.0",
    description="Deterministic local-first code intelligence CLI for code graph extraction and analysis",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "neo4j>=5.0.0",
        "python-dotenv>=1.0.0",
        "PyYAML>=6.0.0",
        "rich>=13.0.0",
        "typer>=0.12,<1.0",
    ],
    extras_require={
        "dev": [
            "build>=1.2",
            "mypy>=1.13",
            "pip-audit>=2.7",
            "pre-commit>=4.0",
            "pytest>=8.0",
            "pytest-cov>=6.0",
            "ruff>=0.8",
        ],
    },
    entry_points={
        "console_scripts": [
            "codegraphx=codegraphx.__main__:main",
        ],
    },
)
