"""
CodeGraphX 2.0 - Metrics Engine (Phase 4)
Separate metrics module computing:
- Cyclomatic complexity
- Depth of inheritance
- Coupling score
- Centrality (degree-based)
- Risk heuristics
"""
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from codegraphx.core.models import (
    ArchNode, ArchRelationship, CPGNode, CPGRelationship,
    MetricsResult, NodeLabel, RelationshipType,
    CPGNodeLabel, CPGRelationshipType, IngestionContext,
)
from codegraphx.core.config import config


class MetricsEngine:
    """Computes structural metrics and risk heuristics."""

    def __init__(self):
        self.results: Dict[str, MetricsResult] = {}

    def compute_all(self, ctx: IngestionContext) -> Dict[str, MetricsResult]:
        """Compute all metrics from context.

        Args:
            ctx: IngestionContext with arch and cpg data populated.

        Returns:
            Dict mapping node_id to MetricsResult.
        """
        # Build lookup structures
        arch_nodes = {n.id: n for n in ctx.arch_nodes}
        arch_rels = ctx.arch_relationships
        cpg_nodes = {n.id: n for n in ctx.cpg_nodes}
        cpg_rels = ctx.cpg_relationships

        # Compute per-function metrics
        for node in ctx.arch_nodes:
            if node.label in (NodeLabel.FUNCTION, NodeLabel.CLASS):
                result = MetricsResult(node_id=node.id)

                # Cyclomatic complexity (from CPG control flow)
                result.cyclomatic_complexity = self._cyclomatic_complexity(
                    node, cpg_nodes, cpg_rels
                )

                # Depth of inheritance (for classes)
                if node.label == NodeLabel.CLASS:
                    result.depth_of_inheritance = self._inheritance_depth(
                        node.id, arch_nodes, arch_rels
                    )

                # Coupling score
                result.coupling_score = self._coupling_score(
                    node.id, arch_rels
                )

                # Centrality
                result.centrality = self._degree_centrality(
                    node.id, arch_rels, len(arch_nodes)
                )

                # Risk flags
                result.risk_flags = self._evaluate_risks(
                    node, result, arch_nodes, arch_rels
                )

                self.results[node.id] = result

        return self.results

    # ── Cyclomatic Complexity ─────────────────────────────────────────────────

    def _cyclomatic_complexity(self, arch_node: ArchNode,
                               cpg_nodes: Dict[str, CPGNode],
                               cpg_rels: List[CPGRelationship]) -> int:
        """Compute cyclomatic complexity: M = E - N + 2P

        Where E = edges, N = nodes, P = connected components (1 for single function).
        We count control flow edges and nodes within this function.
        """
        # Find CPG nodes belonging to this function (by file_path and line range)
        func_start = arch_node.properties.get("start_line", 0)
        func_end = arch_node.properties.get("end_line", 0)
        func_file = arch_node.file_path

        func_cpg_ids: Set[str] = set()
        for cpg_id, cpg_node in cpg_nodes.items():
            if (cpg_node.file_path == func_file and
                    func_start <= cpg_node.start_line <= func_end):
                func_cpg_ids.add(cpg_id)

        if not func_cpg_ids:
            return 1  # Minimum complexity

        # Count control flow edges within this function
        edges = 0
        for rel in cpg_rels:
            if (rel.type in (CPGRelationshipType.FLOWS_TO,
                             CPGRelationshipType.BRANCHES_TO,
                             CPGRelationshipType.RETURNS_TO) and
                    rel.source_id in func_cpg_ids):
                edges += 1

        nodes = len(func_cpg_ids)
        # M = E - N + 2
        complexity = max(1, edges - nodes + 2)
        return complexity

    # ── Depth of Inheritance ──────────────────────────────────────────────────

    def _inheritance_depth(self, class_id: str,
                           arch_nodes: Dict[str, ArchNode],
                           arch_rels: List[ArchRelationship],
                           max_depth: int = 20) -> int:
        """Compute max depth of inheritance chain."""
        # Build parent map
        parent_map: Dict[str, List[str]] = defaultdict(list)
        for rel in arch_rels:
            if rel.type == RelationshipType.INHERITS:
                parent_map[rel.source_id].append(rel.target_id)

        def depth(node_id: str, visited: Set[str]) -> int:
            if node_id in visited or node_id not in parent_map:
                return 0
            visited.add(node_id)
            max_d = 0
            for parent_id in parent_map[node_id]:
                max_d = max(max_d, 1 + depth(parent_id, visited))
            return max_d

        return depth(class_id, set())

    # ── Coupling Score ────────────────────────────────────────────────────────

    def _coupling_score(self, node_id: str,
                        arch_rels: List[ArchRelationship]) -> float:
        """Coupling = number of distinct modules this node depends on / is depended by."""
        connected = set()
        for rel in arch_rels:
            if rel.source_id == node_id:
                connected.add(rel.target_id)
            elif rel.target_id == node_id:
                connected.add(rel.source_id)
        return float(len(connected))

    # ── Degree Centrality ─────────────────────────────────────────────────────

    def _degree_centrality(self, node_id: str,
                           arch_rels: List[ArchRelationship],
                           total_nodes: int) -> float:
        """Degree centrality = (in_degree + out_degree) / (total_nodes - 1)."""
        if total_nodes <= 1:
            return 0.0

        degree = 0
        for rel in arch_rels:
            if rel.source_id == node_id or rel.target_id == node_id:
                degree += 1

        return degree / (total_nodes - 1)

    # ── Risk Heuristics (Phase 4.2) ───────────────────────────────────────────

    def _evaluate_risks(self, node: ArchNode, metrics: MetricsResult,
                        arch_nodes: Dict[str, ArchNode],
                        arch_rels: List[ArchRelationship]) -> List[str]:
        """Flag risk conditions."""
        flags = []
        cfg = config.metrics

        # High complexity + high fan_in
        if (metrics.cyclomatic_complexity > cfg.high_complexity_threshold and
                node.fan_in > 5):
            flags.append(f"HIGH_RISK: complexity={metrics.cyclomatic_complexity}, fan_in={node.fan_in}")

        # Deep dependency chains (> 5 hops)
        chain_depth = self._max_dependency_chain(node.id, arch_rels)
        if chain_depth > cfg.max_dependency_depth:
            flags.append(f"DEEP_CHAIN: depth={chain_depth}")

        # God class
        if node.label == NodeLabel.CLASS:
            total_connections = node.fan_in + node.fan_out
            if total_connections > cfg.god_class_threshold:
                flags.append(f"GOD_CLASS: connections={total_connections}")

        # Tight cyclic cluster detection
        if self._is_in_cycle(node.id, arch_rels):
            flags.append("CYCLIC_DEPENDENCY")

        return flags

    def _max_dependency_chain(self, node_id: str,
                              arch_rels: List[ArchRelationship]) -> int:
        """Find longest dependency chain from this node."""
        adj: Dict[str, Set[str]] = defaultdict(set)
        for rel in arch_rels:
            if rel.type in (RelationshipType.DEPENDS_ON, RelationshipType.CALLS):
                adj[rel.source_id].add(rel.target_id)

        def dfs(nid: str, visited: Set[str]) -> int:
            if nid in visited:
                return 0
            visited.add(nid)
            max_d = 0
            for neighbor in adj.get(nid, []):
                max_d = max(max_d, 1 + dfs(neighbor, visited))
            visited.discard(nid)
            return max_d

        return dfs(node_id, set())

    def _is_in_cycle(self, node_id: str,
                     arch_rels: List[ArchRelationship]) -> bool:
        """Check if node participates in a dependency cycle."""
        adj: Dict[str, Set[str]] = defaultdict(set)
        for rel in arch_rels:
            if rel.type in (RelationshipType.DEPENDS_ON, RelationshipType.IMPORTS, RelationshipType.CALLS):
                adj[rel.source_id].add(rel.target_id)

        # DFS from node_id, check if we can reach node_id again
        visited = set()
        stack = list(adj.get(node_id, []))

        while stack:
            current = stack.pop()
            if current == node_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adj.get(current, []))

        return False
