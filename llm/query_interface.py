"""
CodeGraphX 2.0 - LLM Query Interface (Phase 6)
Natural language to Cypher translation with safety guards.
Subgraph summarization pipeline.
"""
import re
import json
from typing import Optional, Dict, List, Any

from codegraphx.core.models import NodeLabel, RelationshipType, CPGRelationshipType
from codegraphx.core.config import config


# ── Schema Definition for LLM Context ────────────────────────────────────────

SCHEMA_DEFINITION = """
Graph Schema for CodeGraphX 2.0:

Node Labels:
- Repository: id, name, file_path
- Package: id, name, file_path
- Module: id, name, file_path, module
- File: id, name, file_path, module
- Class: id, name, file_path, fan_in, fan_out, instability
- Function: id, name, file_path, fan_in, fan_out, instability, start_line, end_line
- ExternalSymbol: id, name
- Statement: id, name, code, file_path, start_line, end_line
- Expression: id, name, code, file_path, start_line, end_line
- Variable: id, name, code, file_path, start_line
- Parameter: id, name, code, file_path
- Literal: id, name, code, file_path
- ControlStructure: id, name, code, file_path, start_line, end_line

Relationship Types:
- CONTAINS: (Repository)->(Package), (Package)->(File), (File)->(Module), (File)->(Class), (File)->(Function)
- IMPORTS: (File)->(Module|ExternalSymbol)
- CALLS: (Function)->(Function|ExternalSymbol)
- INHERITS: (Class)->(Class|ExternalSymbol)
- IMPLEMENTS: (Class)->(Class)
- DEPENDS_ON: (Module)->(Module|ExternalSymbol)
- AST_PARENT: parent -> child structural
- FLOWS_TO: sequential control flow
- BRANCHES_TO: conditional branching
- RETURNS_TO: return to exit
- DEFINES: statement defines variable
- USES: node uses variable
- DATA_DEPENDS_ON: variable depends on definition

Properties available on nodes:
- fan_in, fan_out, instability (on Function, Class)
- start_line, end_line (on Function, Class, Statement, ControlStructure)
- code (on Function, Statement, Expression, Variable)
- docstring, summary (via semantic enrichment)
"""

ALLOWED_NODE_LABELS = [e.value for e in NodeLabel] + [
    "Statement", "Expression", "Variable", "Parameter", "Literal", "ControlStructure"
]

ALLOWED_RELATIONSHIPS = (
    [e.value for e in RelationshipType] +
    [e.value for e in CPGRelationshipType]
)


# ── Query Validator ───────────────────────────────────────────────────────────

class QueryValidator:
    """Phase 6.1: Validates generated Cypher queries for safety."""

    def __init__(self):
        self.forbidden = [clause.upper() for clause in config.llm.forbidden_clauses]
        self.max_nodes = config.llm.max_result_nodes

    def validate(self, cypher: str) -> Dict[str, Any]:
        """Validate a Cypher query.

        Returns:
            Dict with 'valid' bool, 'errors' list, and 'cleaned' query.
        """
        errors = []

        # Check for forbidden clauses
        upper_query = cypher.upper()
        for clause in self.forbidden:
            # Match as whole word to avoid false positives
            pattern = r'\b' + re.escape(clause) + r'\b'
            if re.search(pattern, upper_query):
                errors.append(f"Forbidden clause detected: {clause}")

        # Check node limit
        if "LIMIT" not in upper_query:
            cypher = cypher.rstrip().rstrip(";") + f" LIMIT {self.max_nodes}"

        # Basic syntax check
        if not cypher.strip().upper().startswith(("MATCH", "RETURN", "WITH", "OPTIONAL", "CALL", "UNWIND")):
            errors.append("Query must start with MATCH, RETURN, WITH, OPTIONAL, CALL, or UNWIND")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "cleaned": cypher if not errors else "",
        }


# ── NL → Cypher Translator ───────────────────────────────────────────────────

class NLToCypherTranslator:
    """Phase 6.1: Translates natural language queries to Cypher.

    Uses a prompt template with schema context. Designed to work with
    any LLM backend (OpenAI, local models, etc).
    """

    def __init__(self):
        self.validator = QueryValidator()

    def build_prompt(self, natural_language_query: str) -> str:
        """Build the LLM prompt for NL → Cypher translation.

        Args:
            natural_language_query: The user's question.

        Returns:
            Complete prompt string to send to an LLM.
        """
        prompt = f"""You are a Cypher query generator for a code analysis graph database.

{SCHEMA_DEFINITION}

Allowed node labels: {', '.join(ALLOWED_NODE_LABELS)}
Allowed relationships: {', '.join(ALLOWED_RELATIONSHIPS)}

RULES:
1. Return ONLY a valid Cypher query. No explanation.
2. NEVER use: CREATE, DELETE, MERGE, SET, REMOVE, DROP
3. Always include a LIMIT clause (max {config.llm.max_result_nodes} nodes)
4. Use MATCH and RETURN only for read operations
5. Use relationship types exactly as listed above

User Question: {natural_language_query}

Cypher Query:"""
        return prompt

    def translate(self, natural_language_query: str,
                  llm_response: str) -> Dict[str, Any]:
        """Process LLM response and validate the Cypher query.

        Args:
            natural_language_query: Original question.
            llm_response: Raw LLM output.

        Returns:
            Dict with validated query or errors.
        """
        # Extract Cypher from response (handle code blocks)
        cypher = self._extract_cypher(llm_response)

        # Validate
        result = self.validator.validate(cypher)
        result["original_query"] = natural_language_query
        result["raw_response"] = llm_response

        return result

    def _extract_cypher(self, response: str) -> str:
        """Extract Cypher query from LLM response, handling code blocks."""
        # Try to extract from code blocks
        code_block = re.search(r'```(?:cypher)?\s*(.*?)```', response, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        # If no code blocks, use the whole response
        lines = response.strip().split("\n")
        cypher_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("//") and not stripped.startswith("#"):
                cypher_lines.append(stripped)

        return " ".join(cypher_lines)


# ── Subgraph Summarization (Phase 6.2) ───────────────────────────────────────

class SubgraphSummarizer:
    """Phase 6.2: Pipeline for summarizing graph query results.

    Pipeline: Cypher → JSON graph → LLM → summary
    """

    def build_summary_prompt(self, graph_json: Dict[str, Any]) -> str:
        """Build prompt for LLM subgraph summarization.

        Args:
            graph_json: JSON representation of the query result subgraph.

        Returns:
            Prompt string for LLM.
        """
        # Serialize graph for LLM context
        nodes_summary = []
        for node in graph_json.get("nodes", []):
            nodes_summary.append(
                f"- [{node.get('label', 'Unknown')}] {node.get('name', '?')} "
                f"(file: {node.get('file_path', '?')}, "
                f"fan_in: {node.get('fan_in', 0)}, fan_out: {node.get('fan_out', 0)})"
            )

        rels_summary = []
        for rel in graph_json.get("relationships", []):
            rels_summary.append(
                f"- ({rel.get('source', '?')}) -[{rel.get('type', '?')}]-> ({rel.get('target', '?')})"
            )

        nodes_text = "\n".join(nodes_summary[:50])  # Limit context
        rels_text = "\n".join(rels_summary[:100])

        prompt = f"""Analyze this code graph and provide a structured summary.

NODES ({len(graph_json.get('nodes', []))} total):
{nodes_text}

RELATIONSHIPS ({len(graph_json.get('relationships', []))} total):
{rels_text}

Provide:
1. Entry points: Which nodes are the main entry points?
2. Major flows: What are the primary execution/dependency flows?
3. Bottlenecks: Which nodes have unusually high connectivity or complexity?

Keep the summary concise and actionable."""

        return prompt

    def format_result_as_json(self, nodes: List[Dict],
                              relationships: List[Dict]) -> Dict[str, Any]:
        """Format query results as JSON for summarization.

        Args:
            nodes: List of node dicts from query results.
            relationships: List of relationship dicts.

        Returns:
            Formatted JSON dict.
        """
        return {
            "nodes": nodes,
            "relationships": relationships,
            "stats": {
                "total_nodes": len(nodes),
                "total_relationships": len(relationships),
                "node_types": list(set(n.get("label", "") for n in nodes)),
                "relationship_types": list(set(r.get("type", "") for r in relationships)),
            }
        }
