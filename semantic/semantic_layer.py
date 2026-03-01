"""
CodeGraphX 2.0 - Semantic Layer (Phase 5)
Enriches nodes with docstrings, comments, summaries, and embeddings.
Provides hybrid retrieval: vector similarity + graph expansion.
"""
import re
from typing import List, Dict, Optional, Tuple
import numpy as np

from codegraphx.core.models import (
    ArchNode, ArchRelationship, SemanticNode, NodeLabel,
    RelationshipType, IngestionContext, generate_id,
)
from codegraphx.core.config import config


class SemanticEnricher:
    """Phase 5.1-5.2: Enriches architectural nodes with semantic properties."""

    def __init__(self, model_name: Optional[str] = None):
        self._model = None
        self._model_name = model_name or config.semantic.model_name
        self.semantic_nodes: Dict[str, SemanticNode] = {}

    def _load_model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except ImportError:
                print("[WARN] sentence-transformers not installed. Using fallback embeddings.")
                self._model = "fallback"

    def enrich(self, ctx: IngestionContext) -> Dict[str, SemanticNode]:
        """Enrich all Class and Function nodes with semantic properties.

        Phase 5.1: Add docstring, comments, summary, embedding
        Phase 5.2: Embed name + docstring + first N lines of body

        Args:
            ctx: IngestionContext with arch_nodes populated.

        Returns:
            Dict mapping node_id to SemanticNode.
        """
        self._load_model()

        for node in ctx.arch_nodes:
            if node.label in (NodeLabel.CLASS, NodeLabel.FUNCTION):
                semantic = SemanticNode(node_id=node.id)

                code = node.properties.get("code", "")

                # Extract docstring
                semantic.docstring = self._extract_docstring(code)

                # Extract comments
                semantic.comments = self._extract_comments(code)

                # Build summary text
                semantic.summary = self._build_summary(node.name, semantic.docstring, code)

                # Generate embedding
                semantic.embedding = self._embed(semantic.summary)

                self.semantic_nodes[node.id] = semantic

        return self.semantic_nodes

    def _extract_docstring(self, code: str) -> str:
        """Extract docstring from function/class code."""
        # Python triple-quote docstrings
        patterns = [
            r'"""(.*?)"""',
            r"'''(.*?)'''",
        ]
        for pattern in patterns:
            match = re.search(pattern, code, re.DOTALL)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_comments(self, code: str) -> str:
        """Extract inline comments from code."""
        comments = []
        for line in code.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#"):
                comments.append(stripped[1:].strip())
            elif stripped.startswith("//"):
                comments.append(stripped[2:].strip())
        return " ".join(comments)

    def _build_summary(self, name: str, docstring: str, code: str) -> str:
        """Build summary text for embedding.

        Phase 5.2: Embed name + docstring + first N lines of body.
        """
        max_lines = config.semantic.max_body_lines
        lines = code.split("\n")[:max_lines]
        body_text = "\n".join(lines)

        parts = [name]
        if docstring:
            parts.append(docstring)
        parts.append(body_text)

        return " ".join(parts)

    def _embed(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        if not text.strip():
            return []

        if self._model == "fallback":
            # Deterministic fallback: hash-based embedding
            return self._fallback_embed(text)

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception:
            return self._fallback_embed(text)

    def _fallback_embed(self, text: str, dim: int = 384) -> List[float]:
        """Simple hash-based fallback embedding for when model isn't available."""
        np.random.seed(hash(text) % (2**32))
        return np.random.randn(dim).tolist()


# ── Hybrid Retrieval (Phase 5.3) ─────────────────────────────────────────────

class HybridRetriever:
    """Phase 5.3: Vector similarity + graph expansion retrieval."""

    def __init__(self, semantic_nodes: Dict[str, SemanticNode],
                 arch_nodes: Dict[str, ArchNode],
                 arch_relationships: List[ArchRelationship]):
        self.semantic_nodes = semantic_nodes
        self.arch_nodes = arch_nodes
        self.relationships = arch_relationships
        self._enricher = SemanticEnricher()

    def query(self, query_text: str,
              top_k: Optional[int] = None,
              expansion_hops: Optional[int] = None) -> List[Dict]:
        """Hybrid retrieval pipeline.

        1. Generate query embedding
        2. Retrieve top K nodes by cosine similarity
        3. Expand 2 hops via CALLS + DEPENDS_ON
        4. Return induced subgraph

        Args:
            query_text: Natural language query.
            top_k: Number of top results (default from config).
            expansion_hops: Number of hops to expand (default from config).

        Returns:
            List of dicts with node info and similarity scores.
        """
        top_k = top_k or config.semantic.top_k
        expansion_hops = expansion_hops or config.semantic.expansion_hops

        self._enricher._load_model()

        # 1. Generate query embedding
        query_embedding = np.array(self._enricher._embed(query_text))
        if len(query_embedding) == 0:
            return []

        # 2. Compute cosine similarity against all semantic nodes
        scored: List[Tuple[str, float]] = []
        for node_id, sem_node in self.semantic_nodes.items():
            if not sem_node.embedding:
                continue
            node_embedding = np.array(sem_node.embedding)
            sim = self._cosine_similarity(query_embedding, node_embedding)
            scored.append((node_id, sim))

        # Sort by similarity, take top K
        scored.sort(key=lambda x: x[1], reverse=True)
        top_nodes = scored[:top_k]

        # 3. Expand via CALLS + DEPENDS_ON
        seed_ids = {node_id for node_id, _ in top_nodes}
        expanded_ids = self._expand_graph(seed_ids, expansion_hops)

        # 4. Build result subgraph
        results = []
        all_ids = seed_ids | expanded_ids
        score_map = dict(top_nodes)

        for node_id in all_ids:
            if node_id not in self.arch_nodes:
                continue
            arch_node = self.arch_nodes[node_id]
            sem_node = self.semantic_nodes.get(node_id)

            results.append({
                "id": node_id,
                "name": arch_node.name,
                "label": arch_node.label.value if hasattr(arch_node.label, 'value') else str(arch_node.label),
                "file_path": arch_node.file_path,
                "similarity": score_map.get(node_id, 0.0),
                "docstring": sem_node.docstring if sem_node else "",
                "is_seed": node_id in seed_ids,
            })

        # Sort: seeds first by similarity, then expanded
        results.sort(key=lambda x: (-x["is_seed"], -x["similarity"]))
        return results

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _expand_graph(self, seed_ids: set, hops: int) -> set:
        """Expand from seed nodes via CALLS and DEPENDS_ON relationships."""
        # Build adjacency
        adj: Dict[str, set] = {}
        expansion_types = {RelationshipType.CALLS, RelationshipType.DEPENDS_ON}

        for rel in self.relationships:
            if rel.type in expansion_types:
                adj.setdefault(rel.source_id, set()).add(rel.target_id)
                adj.setdefault(rel.target_id, set()).add(rel.source_id)

        expanded = set()
        frontier = set(seed_ids)

        for _ in range(hops):
            next_frontier = set()
            for node_id in frontier:
                for neighbor in adj.get(node_id, []):
                    if neighbor not in seed_ids and neighbor not in expanded:
                        next_frontier.add(neighbor)
                        expanded.add(neighbor)
            frontier = next_frontier

        return expanded
