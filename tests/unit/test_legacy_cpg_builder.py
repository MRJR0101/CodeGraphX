from __future__ import annotations

from core.models import ASTNode, CPGRelationshipType, IngestionContext
from graph.cpg_builder import CPGBuilder


def test_ast_parent_edges_only_reference_existing_cpg_nodes() -> None:
    func = ASTNode(
        type="function_definition",
        name="demo",
        file_path="demo.py",
        start_line=1,
        end_line=2,
        children=[
            ASTNode(
                type="return_statement",
                file_path="demo.py",
                start_line=2,
                end_line=2,
                children=[
                    ASTNode(
                        type="identifier",
                        name="value",
                        file_path="demo.py",
                        start_line=2,
                        end_line=2,
                        children=[],
                    )
                ],
            )
        ],
    )

    result = CPGBuilder().build(IngestionContext(repo_path="repo", ast_nodes=[func]))
    node_ids = {node.id for node in result.cpg_nodes}

    ast_parent_edges = [rel for rel in result.cpg_relationships if rel.type == CPGRelationshipType.AST_PARENT]

    assert ast_parent_edges
    for rel in ast_parent_edges:
        assert rel.source_id in node_ids
        assert rel.target_id in node_ids
