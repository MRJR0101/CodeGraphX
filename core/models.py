"""
CodeGraphX 2.0 - Core Data Models
Pydantic models for AST nodes, architectural graph nodes, and CPG nodes.
"""
import uuid
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_id() -> str:
    """Generate a unique node ID."""
    return str(uuid.uuid4())


# ── Enums ─────────────────────────────────────────────────────────────────────

class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"


class NodeLabel(str, Enum):
    """Phase 2 - Architectural Graph node labels."""
    REPOSITORY = "Repository"
    PACKAGE = "Package"
    MODULE = "Module"
    FILE = "File"
    CLASS = "Class"
    FUNCTION = "Function"
    EXTERNAL_SYMBOL = "ExternalSymbol"


class CPGNodeLabel(str, Enum):
    """Phase 3 - Code Property Graph node labels."""
    STATEMENT = "Statement"
    EXPRESSION = "Expression"
    VARIABLE = "Variable"
    PARAMETER = "Parameter"
    LITERAL = "Literal"
    CONTROL_STRUCTURE = "ControlStructure"


class RelationshipType(str, Enum):
    """Phase 2 - Architectural relationships."""
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"
    DEPENDS_ON = "DEPENDS_ON"


class CPGRelationshipType(str, Enum):
    """Phase 3 - CPG relationships."""
    # Structural
    AST_PARENT = "AST_PARENT"
    # Control flow
    FLOWS_TO = "FLOWS_TO"
    BRANCHES_TO = "BRANCHES_TO"
    RETURNS_TO = "RETURNS_TO"
    # Data flow
    DEFINES = "DEFINES"
    USES = "USES"
    DATA_DEPENDS_ON = "DATA_DEPENDS_ON"


# ── Phase 1: AST Node Model ──────────────────────────────────────────────────

class ASTNode(BaseModel):
    """Core AST node extracted from source code (Phase 1.2)."""
    id: str = Field(default_factory=generate_id)
    type: str                        # e.g. "function_definition", "class_definition"
    name: Optional[str] = None       # identifier name if applicable
    code: str = ""                   # source code text
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    children: List["ASTNode"] = Field(default_factory=list)
    language: Language = Language.PYTHON

    model_config = ConfigDict(use_enum_values=True)


# ── Phase 2: Architectural Graph Models ───────────────────────────────────────

class ArchNode(BaseModel):
    """Node in the Architectural Knowledge Graph."""
    id: str = Field(default_factory=generate_id)
    label: NodeLabel
    name: str
    file_path: str = ""
    module: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)
    # Phase 2.4 metrics
    fan_in: int = 0
    fan_out: int = 0
    instability: float = 0.0


class ArchRelationship(BaseModel):
    """Relationship in the Architectural Knowledge Graph."""
    source_id: str
    target_id: str
    type: RelationshipType
    properties: Dict[str, Any] = Field(default_factory=dict)


# ── Phase 3: CPG Models ──────────────────────────────────────────────────────

class CPGNode(BaseModel):
    """Node in the Code Property Graph."""
    id: str = Field(default_factory=generate_id)
    label: CPGNodeLabel
    name: str = ""
    code: str = ""
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    parent_function_id: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class CPGRelationship(BaseModel):
    """Relationship in the Code Property Graph."""
    source_id: str
    target_id: str
    type: CPGRelationshipType
    properties: Dict[str, Any] = Field(default_factory=dict)


# ── Phase 4: Metrics Models ──────────────────────────────────────────────────

class MetricsResult(BaseModel):
    """Computed metrics for a node."""
    node_id: str
    cyclomatic_complexity: int = 0
    depth_of_inheritance: int = 0
    coupling_score: float = 0.0
    centrality: float = 0.0
    risk_flags: List[str] = Field(default_factory=list)


# ── Phase 5: Semantic Models ─────────────────────────────────────────────────

class SemanticNode(BaseModel):
    """Enriched semantic properties for a node."""
    node_id: str
    docstring: str = ""
    comments: str = ""
    summary: str = ""
    embedding: List[float] = Field(default_factory=list)


# ── Ingestion Context ────────────────────────────────────────────────────────

class IngestionContext(BaseModel):
    """Tracks state during repository ingestion."""
    repo_path: str
    repo_id: str = Field(default_factory=generate_id)
    language: Language = Language.PYTHON
    ast_nodes: List[ASTNode] = Field(default_factory=list)
    arch_nodes: List[ArchNode] = Field(default_factory=list)
    arch_relationships: List[ArchRelationship] = Field(default_factory=list)
    cpg_nodes: List[CPGNode] = Field(default_factory=list)
    cpg_relationships: List[CPGRelationship] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
