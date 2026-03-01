"""
CodeGraphX 2.0 - Ingestion Pipeline
Orchestrates all phases in the correct build order:
Phase 1 → Parse AST
Phase 2 → Architecture Graph
Phase 3 → Code Property Graph
Phase 4 → Metrics
Phase 5 → Semantic Enrichment
Phase 6 → (LLM Interface - query time only)
Phase 7 → Hardening checks
"""
from pathlib import Path
from typing import Optional, Dict, Any

from codegraphx.core.models import IngestionContext, Language, generate_id
from codegraphx.core.config import config
from codegraphx.core.hardening import (
    DeterminismChecker, PerformanceMonitor, QueryGuard,
)
from codegraphx.parsers.tree_sitter_parser import parse_repository, count_functions, count_classes
from codegraphx.extractors.architecture_extractor import ArchitectureExtractor, ArchitectureValidator
from codegraphx.graph.cpg_builder import CPGBuilder
from codegraphx.metrics.metrics_engine import MetricsEngine
from codegraphx.semantic.semantic_layer import SemanticEnricher, HybridRetriever


class IngestionPipeline:
    """Runs the full ingestion pipeline through all phases."""

    def __init__(self, neo4j_connection=None):
        self.connection = neo4j_connection
        self.monitor = PerformanceMonitor()
        self.context: Optional[IngestionContext] = None
        self.metrics_results = {}
        self.semantic_nodes = {}
        self._retriever: Optional[HybridRetriever] = None

    def ingest(self, repo_path: str, language: str = "python",
               write_to_neo4j: bool = False,
               skip_semantic: bool = False) -> IngestionContext:
        """Run full ingestion pipeline.

        Args:
            repo_path: Path to repository root.
            language: Primary language ("python" or "javascript").
            write_to_neo4j: Whether to persist to Neo4j.
            skip_semantic: Skip Phase 5 (useful if no model available).

        Returns:
            Completed IngestionContext.
        """
        repo = Path(repo_path).resolve()
        if not repo.is_dir():
            raise ValueError(f"Repository not found: {repo_path}")

        ctx = IngestionContext(
            repo_path=str(repo),
            repo_id=generate_id(),
            language=Language(language),
        )

        self.monitor.start("ingestion")

        # ── Phase 1: Parse AST ────────────────────────────────────────────
        print(f"[Phase 1] Parsing repository: {repo}")
        self.monitor.start("phase1_parsing")

        ctx.ast_nodes = parse_repository(str(repo))

        total_functions = sum(count_functions(ast) for ast in ctx.ast_nodes)
        total_classes = sum(count_classes(ast) for ast in ctx.ast_nodes)

        elapsed = self.monitor.stop("phase1_parsing")
        print(f"  ✓ Parsed {len(ctx.ast_nodes)} files, "
              f"{total_functions} functions, {total_classes} classes "
              f"({elapsed:.3f}s)")

        # ── Phase 2: Architectural Knowledge Graph ────────────────────────
        print("[Phase 2] Building Architectural Knowledge Graph...")
        self.monitor.start("phase2_architecture")

        extractor = ArchitectureExtractor()
        ctx = extractor.extract(ctx)

        elapsed = self.monitor.stop("phase2_architecture")
        print(f"  ✓ {len(ctx.arch_nodes)} nodes, "
              f"{len(ctx.arch_relationships)} relationships ({elapsed:.3f}s)")

        # Phase 2.5 Validation
        validator = ArchitectureValidator(extractor)
        cycles = validator.find_circular_dependencies()
        dead = validator.find_dead_modules()
        hotspots = validator.find_dependency_hotspots(5)

        if cycles:
            print(f"  ⚠ {len(cycles)} circular dependencies detected")
        if dead:
            print(f"  ⚠ {len(dead)} dead modules (no incoming edges)")
        if hotspots:
            top_name, top_count = hotspots[0]
            print(f"  ℹ Top hotspot: {top_name} ({top_count} connections)")

        # ── Phase 3: Code Property Graph ──────────────────────────────────
        print("[Phase 3] Building Code Property Graph...")
        self.monitor.start("phase3_cpg")

        cpg_builder = CPGBuilder()
        ctx = cpg_builder.build(ctx)

        elapsed = self.monitor.stop("phase3_cpg")
        print(f"  ✓ {len(ctx.cpg_nodes)} CPG nodes, "
              f"{len(ctx.cpg_relationships)} CPG relationships ({elapsed:.3f}s)")

        # ── Phase 4: Metrics ──────────────────────────────────────────────
        print("[Phase 4] Computing metrics...")
        self.monitor.start("phase4_metrics")

        engine = MetricsEngine()
        self.metrics_results = engine.compute_all(ctx)

        risk_count = sum(1 for m in self.metrics_results.values() if m.risk_flags)
        elapsed = self.monitor.stop("phase4_metrics")
        print(f"  ✓ Metrics computed for {len(self.metrics_results)} nodes, "
              f"{risk_count} risk flags ({elapsed:.3f}s)")

        # ── Phase 5: Semantic Layer ───────────────────────────────────────
        if not skip_semantic:
            print("[Phase 5] Enriching with semantic data...")
            self.monitor.start("phase5_semantic")

            enricher = SemanticEnricher()
            self.semantic_nodes = enricher.enrich(ctx)

            # Set up retriever
            arch_nodes_dict = {n.id: n for n in ctx.arch_nodes}
            self._retriever = HybridRetriever(
                self.semantic_nodes, arch_nodes_dict, ctx.arch_relationships
            )

            elapsed = self.monitor.stop("phase5_semantic")
            print(f"  ✓ {len(self.semantic_nodes)} nodes enriched ({elapsed:.3f}s)")
        else:
            print("[Phase 5] Skipped (--skip-semantic)")

        # ── Phase 7: Hardening ────────────────────────────────────────────
        fingerprint = DeterminismChecker.compute_repo_fingerprint(ctx)
        print(f"[Phase 7] Repo fingerprint: {fingerprint[:16]}...")

        # ── Write to Neo4j (optional) ─────────────────────────────────────
        if write_to_neo4j and self.connection:
            print("[Neo4j] Writing to database...")
            self.monitor.start("neo4j_write")

            from codegraphx.graph.writer import GraphWriter
            writer = GraphWriter(self.connection)
            writer.write_architecture(ctx)
            writer.write_cpg(ctx)
            writer.write_metrics(self.metrics_results)
            if self.semantic_nodes:
                writer.write_semantic(self.semantic_nodes)

            elapsed = self.monitor.stop("neo4j_write")
            print(f"  ✓ Written to Neo4j ({elapsed:.3f}s)")

        total_elapsed = self.monitor.stop("ingestion")
        print(f"\n[DONE] Total ingestion time: {total_elapsed:.3f}s")

        # Performance report
        report = self.monitor.report()
        for phase, timing in report.items():
            print(f"  {phase}: {timing}")

        self.context = ctx
        return ctx

    def semantic_query(self, question: str) -> list:
        """Run a semantic query against the enriched graph.

        Args:
            question: Natural language question.

        Returns:
            List of matching results.
        """
        if not self._retriever:
            raise RuntimeError("Semantic layer not initialized. Run ingest() first without --skip-semantic.")
        return self._retriever.query(question)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of computed metrics."""
        if not self.metrics_results:
            return {"error": "No metrics computed. Run ingest() first."}

        complexities = [m.cyclomatic_complexity for m in self.metrics_results.values()]
        risk_nodes = [m for m in self.metrics_results.values() if m.risk_flags]

        return {
            "total_nodes_analyzed": len(self.metrics_results),
            "avg_complexity": sum(complexities) / len(complexities) if complexities else 0,
            "max_complexity": max(complexities) if complexities else 0,
            "risk_flagged_nodes": len(risk_nodes),
            "risk_details": [
                {"node_id": m.node_id, "flags": m.risk_flags}
                for m in risk_nodes
            ],
        }
