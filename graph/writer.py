"""
CodeGraphX 2.0 - Graph Writer
Persists Architectural and CPG data to Neo4j.
"""
from typing import Dict

from codegraphx.core.models import (
    ArchNode, ArchRelationship, CPGNode, CPGRelationship,
    IngestionContext, MetricsResult, SemanticNode,
)
from codegraphx.schema.neo4j_schema import Neo4jConnection


class GraphWriter:
    """Writes ingestion results to Neo4j."""

    def __init__(self, connection: Neo4jConnection):
        self.conn = connection

    def write_architecture(self, ctx: IngestionContext):
        """Write architectural graph nodes and relationships to Neo4j."""
        with self.conn.session() as session:
            # Write nodes in batches
            for node in ctx.arch_nodes:
                self._write_arch_node(session, node)

            # Write relationships
            for rel in ctx.arch_relationships:
                self._write_arch_relationship(session, rel)

    def write_cpg(self, ctx: IngestionContext):
        """Write Code Property Graph nodes and relationships to Neo4j."""
        with self.conn.session() as session:
            for node in ctx.cpg_nodes:
                self._write_cpg_node(session, node)

            for rel in ctx.cpg_relationships:
                self._write_cpg_relationship(session, rel)

    def write_metrics(self, metrics: Dict[str, MetricsResult]):
        """Write computed metrics as node properties."""
        with self.conn.session() as session:
            for node_id, result in metrics.items():
                session.run("""
                    MATCH (n {id: $id})
                    SET n.cyclomatic_complexity = $cc,
                        n.depth_of_inheritance = $doi,
                        n.coupling_score = $coupling,
                        n.centrality = $centrality,
                        n.risk_flags = $risk_flags
                """, {
                    "id": node_id,
                    "cc": result.cyclomatic_complexity,
                    "doi": result.depth_of_inheritance,
                    "coupling": result.coupling_score,
                    "centrality": result.centrality,
                    "risk_flags": result.risk_flags,
                })

    def write_semantic(self, semantic_nodes: Dict[str, SemanticNode]):
        """Write semantic enrichment to node properties."""
        with self.conn.session() as session:
            for node_id, sem in semantic_nodes.items():
                session.run("""
                    MATCH (n {id: $id})
                    SET n.docstring = $docstring,
                        n.comments = $comments,
                        n.summary = $summary,
                        n.embedding = $embedding
                """, {
                    "id": node_id,
                    "docstring": sem.docstring,
                    "comments": sem.comments,
                    "summary": sem.summary,
                    "embedding": sem.embedding,
                })

    # ── Internal Writers ──────────────────────────────────────────────────────

    def _write_arch_node(self, session, node: ArchNode):
        """Write a single architectural node."""
        label = node.label.value if hasattr(node.label, 'value') else str(node.label)
        props = {
            "id": node.id,
            "name": node.name,
            "file_path": node.file_path,
            "module": node.module,
            "fan_in": node.fan_in,
            "fan_out": node.fan_out,
            "instability": node.instability,
        }
        # Merge additional properties
        for k, v in node.properties.items():
            if isinstance(v, (str, int, float, bool)):
                props[k] = v

        # Build property string for Cypher
        prop_assignments = ", ".join(f"n.{k} = ${k}" for k in props.keys())

        query = f"""
            MERGE (n:{label} {{id: $id}})
            SET {prop_assignments}
        """
        session.run(query, props)

    def _write_arch_relationship(self, session, rel: ArchRelationship):
        """Write a single architectural relationship."""
        rel_type = rel.type.value if hasattr(rel.type, 'value') else str(rel.type)
        session.run(f"""
            MATCH (a {{id: $source_id}})
            MATCH (b {{id: $target_id}})
            MERGE (a)-[r:{rel_type}]->(b)
        """, {
            "source_id": rel.source_id,
            "target_id": rel.target_id,
        })

    def _write_cpg_node(self, session, node: CPGNode):
        """Write a single CPG node."""
        label = node.label.value if hasattr(node.label, 'value') else str(node.label)
        session.run(f"""
            MERGE (n:{label} {{id: $id}})
            SET n.name = $name,
                n.code = $code,
                n.file_path = $file_path,
                n.start_line = $start_line,
                n.end_line = $end_line,
                n.parent_function_id = $parent_function_id
        """, {
            "id": node.id,
            "name": node.name,
            "code": node.code[:500] if node.code else "",
            "file_path": node.file_path,
            "start_line": node.start_line,
            "end_line": node.end_line,
            "parent_function_id": node.parent_function_id or "",
        })

    def _write_cpg_relationship(self, session, rel: CPGRelationship):
        """Write a single CPG relationship."""
        rel_type = rel.type.value if hasattr(rel.type, 'value') else str(rel.type)
        session.run(f"""
            MATCH (a {{id: $source_id}})
            MATCH (b {{id: $target_id}})
            MERGE (a)-[r:{rel_type}]->(b)
        """, {
            "source_id": rel.source_id,
            "target_id": rel.target_id,
        })
