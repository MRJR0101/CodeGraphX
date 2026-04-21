"""
CodeGraphX 2.0 - Code Property Graph Layer (Phase 3)
Augments the Architectural Graph with deep semantic structure:
- Additional node labels: Statement, Expression, Variable, Parameter, Literal, ControlStructure
- Control flow: FLOWS_TO, BRANCHES_TO, RETURNS_TO
- Data flow: DEFINES, USES, DATA_DEPENDS_ON
- Scope: intra-procedural only
"""
from typing import List, Dict, Optional

from core.models import (
    ASTNode, CPGNode, CPGRelationship, CPGNodeLabel, CPGRelationshipType,
    IngestionContext, generate_id,
)
from parsers.tree_sitter_parser import collect_nodes_by_type, FUNCTION_TYPES


# ── Node Type Mapping ─────────────────────────────────────────────────────────

STATEMENT_TYPES = {
    # Python
    "expression_statement", "return_statement", "assert_statement",
    "raise_statement", "pass_statement", "break_statement",
    "continue_statement", "delete_statement", "global_statement",
    "nonlocal_statement", "print_statement",
    # JS
    "throw_statement", "variable_declaration", "lexical_declaration",
}

EXPRESSION_TYPES = {
    # Python
    "call", "binary_expression", "unary_expression", "comparison_operator",
    "boolean_operator", "not_operator", "conditional_expression",
    "subscript", "attribute", "slice",
    # JS
    "call_expression", "ternary_expression", "member_expression",
}

CONTROL_TYPES = {
    # Python
    "if_statement", "for_statement", "while_statement",
    "try_statement", "with_statement", "match_statement",
    # JS
    "for_in_statement", "do_statement", "switch_statement",
}

VARIABLE_TYPES = {"identifier"}
PARAMETER_TYPES = {"parameters", "typed_parameter", "default_parameter", "typed_default_parameter"}
LITERAL_TYPES = {"string", "integer", "float", "true", "false", "none", "number", "template_string"}


# ── CPG Builder ───────────────────────────────────────────────────────────────

class CPGBuilder:
    """Builds Code Property Graph from AST nodes."""

    def __init__(self) -> None:
        self.nodes: Dict[str, CPGNode] = {}
        self.relationships: List[CPGRelationship] = []
        self._ast_to_cpg: Dict[str, str] = {}  # ast_node_id -> cpg_node_id

    def build(self, ctx: IngestionContext) -> IngestionContext:
        """Build CPG from all parsed AST trees.

        Args:
            ctx: IngestionContext with ast_nodes populated.

        Returns:
            Updated IngestionContext with cpg_nodes and cpg_relationships.
        """
        for ast_root in ctx.ast_nodes:
            # Process each function independently (intra-procedural)
            functions = collect_nodes_by_type(ast_root, FUNCTION_TYPES)
            for func in functions:
                self._process_function(func)

        ctx.cpg_nodes = list(self.nodes.values())
        ctx.cpg_relationships = self.relationships
        return ctx

    # ── Function Processing ───────────────────────────────────────────────────

    def _process_function(self, func_ast: ASTNode) -> None:
        """Process a single function: extract CPG nodes, control flow, data flow."""
        func_cpg_id = generate_id()

        # 1. Extract all CPG nodes from function body
        body_nodes = self._extract_cpg_nodes(func_ast, func_cpg_id)

        # 2. Build AST_PARENT relationships between concrete CPG nodes only.
        self._build_ast_parents(func_ast, None)

        # 3. Build control flow graph
        self._build_control_flow(func_ast, body_nodes)

        # 4. Build data flow (define-use chains)
        self._build_data_flow(body_nodes)

    def _extract_cpg_nodes(self, ast_node: ASTNode,
                           parent_func_id: str) -> List[CPGNode]:
        """Recursively extract CPG nodes from AST."""
        results = []
        cpg_node = self._classify_and_create(ast_node, parent_func_id)
        if cpg_node:
            results.append(cpg_node)

        for child in ast_node.children:
            results.extend(self._extract_cpg_nodes(child, parent_func_id))

        return results

    def _classify_and_create(self, ast_node: ASTNode,
                             parent_func_id: str) -> Optional[CPGNode]:
        """Classify AST node type and create appropriate CPG node."""
        label = self._classify_node(ast_node.type)
        if label is None:
            return None

        cpg_node = CPGNode(
            id=generate_id(),
            label=label,
            name=ast_node.name or "",
            code=ast_node.code[:500] if ast_node.code else "",
            file_path=ast_node.file_path,
            start_line=ast_node.start_line,
            end_line=ast_node.end_line,
            parent_function_id=parent_func_id,
        )
        self.nodes[cpg_node.id] = cpg_node
        self._ast_to_cpg[ast_node.id] = cpg_node.id
        return cpg_node

    def _classify_node(self, node_type: str) -> Optional[CPGNodeLabel]:
        """Map tree-sitter node type to CPG label."""
        if node_type in STATEMENT_TYPES:
            return CPGNodeLabel.STATEMENT
        elif node_type in EXPRESSION_TYPES:
            return CPGNodeLabel.EXPRESSION
        elif node_type in CONTROL_TYPES:
            return CPGNodeLabel.CONTROL_STRUCTURE
        elif node_type in VARIABLE_TYPES:
            return CPGNodeLabel.VARIABLE
        elif node_type in PARAMETER_TYPES:
            return CPGNodeLabel.PARAMETER
        elif node_type in LITERAL_TYPES:
            return CPGNodeLabel.LITERAL
        return None

    # ── AST Parent Relationships ──────────────────────────────────────────────

    def _build_ast_parents(self, ast_node: ASTNode, parent_cpg_id: Optional[str]) -> None:
        """Build AST_PARENT relationships."""
        current_cpg_id = self._ast_to_cpg.get(ast_node.id)

        if current_cpg_id and parent_cpg_id and current_cpg_id != parent_cpg_id:
            self.relationships.append(CPGRelationship(
                source_id=parent_cpg_id,
                target_id=current_cpg_id,
                type=CPGRelationshipType.AST_PARENT,
            ))

        effective_parent = current_cpg_id or parent_cpg_id
        for child in ast_node.children:
            self._build_ast_parents(child, effective_parent)

    # ── Control Flow ──────────────────────────────────────────────────────────

    def _build_control_flow(self, func_ast: ASTNode, cpg_nodes: List[CPGNode]) -> None:
        """Build control flow graph for a function.

        Rules:
        - Sequential statements → FLOWS_TO
        - If → BRANCHES_TO for then/else
        - Loops → back-edge to head
        - Return → RETURNS_TO exit
        """
        # Get ordered statements in function body
        statements = [n for n in cpg_nodes
                      if n.label in (CPGNodeLabel.STATEMENT, CPGNodeLabel.CONTROL_STRUCTURE)]
        statements.sort(key=lambda n: n.start_line)

        if not statements:
            return

        # Create virtual exit node
        exit_node = CPGNode(
            id=generate_id(),
            label=CPGNodeLabel.STATEMENT,
            name="__exit__",
            file_path=func_ast.file_path,
            start_line=func_ast.end_line,
            end_line=func_ast.end_line,
            parent_function_id=None,
        )
        self.nodes[exit_node.id] = exit_node

        # Sequential FLOWS_TO
        for i in range(len(statements) - 1):
            self.relationships.append(CPGRelationship(
                source_id=statements[i].id,
                target_id=statements[i + 1].id,
                type=CPGRelationshipType.FLOWS_TO,
            ))

        # Last statement flows to exit
        self.relationships.append(CPGRelationship(
            source_id=statements[-1].id,
            target_id=exit_node.id,
            type=CPGRelationshipType.FLOWS_TO,
        ))

        # Control structures
        for node in cpg_nodes:
            if node.label == CPGNodeLabel.CONTROL_STRUCTURE:
                # BRANCHES_TO for if/switch
                if "if" in node.code[:20].lower() or "switch" in node.code[:20].lower():
                    # Find next statement after this control structure
                    next_stmts = [s for s in statements if s.start_line > node.end_line]
                    if next_stmts:
                        self.relationships.append(CPGRelationship(
                            source_id=node.id,
                            target_id=next_stmts[0].id,
                            type=CPGRelationshipType.BRANCHES_TO,
                        ))

                # Back-edge for loops
                if "for" in node.code[:20].lower() or "while" in node.code[:20].lower():
                    self.relationships.append(CPGRelationship(
                        source_id=node.id,
                        target_id=node.id,  # self-loop back-edge
                        type=CPGRelationshipType.FLOWS_TO,
                        properties={"back_edge": True},
                    ))

            # Return statements
            if node.label == CPGNodeLabel.STATEMENT and "return" in (node.code or "")[:10].lower():
                self.relationships.append(CPGRelationship(
                    source_id=node.id,
                    target_id=exit_node.id,
                    type=CPGRelationshipType.RETURNS_TO,
                ))

    # ── Data Flow ─────────────────────────────────────────────────────────────

    def _build_data_flow(self, cpg_nodes: List[CPGNode]) -> None:
        """Build intra-procedural data flow: DEFINES, USES, DATA_DEPENDS_ON.

        Track assignments → DEFINES
        Track usage → connect to last definition (DATA_DEPENDS_ON)
        """
        # Collect all variable nodes
        variables = [n for n in cpg_nodes if n.label == CPGNodeLabel.VARIABLE]

        # Track definitions: var_name -> latest defining CPG node ID
        definitions: Dict[str, str] = {}

        # Sort by line number for sequential processing
        variables.sort(key=lambda n: n.start_line)

        for var_node in variables:
            var_name = var_node.name
            if not var_name:
                continue

            # Determine if this is a definition or use
            is_def = self._is_definition_context(var_node, cpg_nodes)

            if is_def:
                # DEFINES relationship
                definitions[var_name] = var_node.id
                # Find the statement containing this variable
                stmt = self._find_containing_statement(var_node, cpg_nodes)
                if stmt:
                    self.relationships.append(CPGRelationship(
                        source_id=stmt.id,
                        target_id=var_node.id,
                        type=CPGRelationshipType.DEFINES,
                    ))
            else:
                # USES relationship - connect to last definition
                if var_name in definitions:
                    self.relationships.append(CPGRelationship(
                        source_id=var_node.id,
                        target_id=definitions[var_name],
                        type=CPGRelationshipType.DATA_DEPENDS_ON,
                    ))

    def _is_definition_context(self, var_node: CPGNode,
                               all_nodes: List[CPGNode]) -> bool:
        """Heuristic: check if variable appears in an assignment context."""
        # Check if there's an assignment expression on the same line
        for node in all_nodes:
            if (node.start_line == var_node.start_line and
                    node.label == CPGNodeLabel.STATEMENT):
                code = node.code or ""
                # Simple heuristic: variable is on left side of =
                if "=" in code and not code.strip().startswith("return"):
                    eq_pos = code.index("=")
                    var_pos = code.find(var_node.name)
                    if var_pos >= 0 and var_pos < eq_pos:
                        return True
        return False

    def _find_containing_statement(self, node: CPGNode,
                                   all_nodes: List[CPGNode]) -> Optional[CPGNode]:
        """Find the statement containing a given node."""
        for candidate in all_nodes:
            if (candidate.label == CPGNodeLabel.STATEMENT and
                    candidate.start_line <= node.start_line <= candidate.end_line):
                return candidate
        return None
