"""
CodeGraphX 2.0 - Test Suite
Validates all phases: parsing, architecture, CPG, metrics, semantic, LLM, hardening.
"""
import os
import sys
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Test Fixtures ─────────────────────────────────────────────────────────────

SAMPLE_PYTHON = '''
"""Sample module for testing."""

import os
from pathlib import Path


class BaseProcessor:
    """Base class for processors."""

    def __init__(self, name):
        self.name = name
        self.data = []

    def process(self, item):
        """Process a single item."""
        result = self._transform(item)
        self.data.append(result)
        return result

    def _transform(self, item):
        return str(item).upper()


class AdvancedProcessor(BaseProcessor):
    """Advanced processor with filtering."""

    def __init__(self, name, threshold=10):
        super().__init__(name)
        self.threshold = threshold

    def process(self, item):
        """Override: process with threshold check."""
        if item > self.threshold:
            return super().process(item)
        return None

    def batch_process(self, items):
        """Process multiple items."""
        results = []
        for item in items:
            result = self.process(item)
            if result is not None:
                results.append(result)
        return results


def helper_function(x, y):
    """A standalone helper."""
    return x + y


def main():
    """Entry point."""
    proc = AdvancedProcessor("test", threshold=5)
    data = [1, 10, 20, 3, 15]
    results = proc.batch_process(data)
    total = helper_function(len(results), 0)
    print(f"Processed {total} items")
    return results
'''

SAMPLE_JAVASCRIPT = '''
// Sample JavaScript module

import { readFile } from 'fs';

class DataLoader {
    constructor(path) {
        this.path = path;
        this.cache = {};
    }

    async load(key) {
        if (this.cache[key]) {
            return this.cache[key];
        }
        const data = await this.fetchData(key);
        this.cache[key] = data;
        return data;
    }

    async fetchData(key) {
        return new Promise((resolve) => {
            readFile(this.path + '/' + key, 'utf8', (err, data) => {
                resolve(data);
            });
        });
    }
}

function processData(loader, keys) {
    const results = [];
    for (const key of keys) {
        const value = loader.load(key);
        results.push(value);
    }
    return results;
}

export { DataLoader, processData };
'''


def create_test_repo():
    """Create a temporary test repository."""
    repo_dir = tempfile.mkdtemp(prefix="codegraphx_test_")
    src_dir = os.path.join(repo_dir, "src")
    os.makedirs(src_dir)

    # Python files
    with open(os.path.join(src_dir, "processor.py"), "w") as f:
        f.write(SAMPLE_PYTHON)

    with open(os.path.join(src_dir, "__init__.py"), "w") as f:
        f.write("# src package\n")

    # JavaScript files
    with open(os.path.join(src_dir, "loader.js"), "w") as f:
        f.write(SAMPLE_JAVASCRIPT)

    return repo_dir


# ── Phase 1 Tests: Parsing ────────────────────────────────────────────────────

def test_phase1_parsing():
    """Phase 1 Validation: Parse repository without crash, count functions/classes."""
    print("\n═══ Phase 1: Core Parsing Engine ═══")

    from codegraphx.parsers.tree_sitter_parser import (
        parse_file, parse_repository, count_functions, count_classes
    )

    repo = create_test_repo()
    try:
        # Test: Parse repository without crash
        ast_roots = parse_repository(repo)
        assert len(ast_roots) > 0, "Should parse at least one file"
        print(f"  ✓ Parsed {len(ast_roots)} files without crash")

        # Test: Count functions correctly
        py_file = os.path.join(repo, "src", "processor.py")
        ast = parse_file(py_file)
        assert ast is not None, "Should parse Python file"

        func_count = count_functions(ast)
        assert func_count >= 6, f"Expected >= 6 functions, got {func_count}"
        print(f"  ✓ Counted {func_count} functions correctly")

        # Test: Count classes correctly
        class_count = count_classes(ast)
        assert class_count >= 2, f"Expected >= 2 classes, got {class_count}"
        print(f"  ✓ Counted {class_count} classes correctly")

        # Test: AST node properties
        assert ast.id is not None
        assert ast.type == "module"
        assert ast.file_path == py_file
        print("  ✓ AST node properties correct")

        # Test: JavaScript parsing
        js_file = os.path.join(repo, "src", "loader.js")
        js_ast = parse_file(js_file)
        assert js_ast is not None, "Should parse JavaScript file"
        js_funcs = count_functions(js_ast)
        assert js_funcs >= 1, f"Expected >= 1 JS function, got {js_funcs}"
        print(f"  ✓ Parsed JavaScript: {js_funcs} functions")

        print("  ✓ Phase 1 PASSED")
        return ast_roots

    finally:
        shutil.rmtree(repo)


# ── Phase 2 Tests: Architectural Graph ────────────────────────────────────────

def test_phase2_architecture():
    """Phase 2 Validation: Architectural graph extraction and validation queries."""
    print("\n═══ Phase 2: Architectural Knowledge Graph ═══")

    from codegraphx.core.models import IngestionContext, Language, NodeLabel
    from codegraphx.parsers.tree_sitter_parser import parse_repository
    from codegraphx.extractors.architecture_extractor import (
        ArchitectureExtractor, ArchitectureValidator
    )

    repo = create_test_repo()
    try:
        ctx = IngestionContext(repo_path=repo, language=Language.PYTHON)
        ctx.ast_nodes = parse_repository(repo)

        extractor = ArchitectureExtractor()
        ctx = extractor.extract(ctx)

        # Test: Node creation
        assert len(ctx.arch_nodes) > 0, "Should create arch nodes"
        labels = set(n.label for n in ctx.arch_nodes)
        assert NodeLabel.REPOSITORY in labels, "Should have Repository node"
        assert NodeLabel.FILE in labels, "Should have File nodes"
        assert NodeLabel.FUNCTION in labels, "Should have Function nodes"
        print(f"  ✓ Created {len(ctx.arch_nodes)} architectural nodes")

        # Test: Relationship creation
        assert len(ctx.arch_relationships) > 0, "Should create relationships"
        rel_types = set(r.type for r in ctx.arch_relationships)
        print(f"  ✓ Created {len(ctx.arch_relationships)} relationships: {[r.value for r in rel_types]}")

        # Test: Fan-in/fan-out metrics
        functions = [n for n in ctx.arch_nodes if n.label == NodeLabel.FUNCTION]
        has_metrics = any(n.fan_in > 0 or n.fan_out > 0 for n in functions)
        print(f"  ✓ Fan-in/fan-out computed (active: {has_metrics})")

        # Test: Validation queries
        validator = ArchitectureValidator(extractor)

        cycles = validator.find_circular_dependencies()
        print(f"  ✓ Circular dependency detection: {len(cycles)} found")

        dead = validator.find_dead_modules()
        print(f"  ✓ Dead module detection: {len(dead)} found")

        hotspots = validator.find_dependency_hotspots(5)
        print(f"  ✓ Dependency hotspots: {len(hotspots)} found")

        print("  ✓ Phase 2 PASSED")
        return ctx

    finally:
        shutil.rmtree(repo)


# ── Phase 3 Tests: Code Property Graph ────────────────────────────────────────

def test_phase3_cpg():
    """Phase 3 Validation: CPG construction with control and data flow."""
    print("\n═══ Phase 3: Code Property Graph ═══")

    from codegraphx.core.models import IngestionContext, Language, CPGNodeLabel, CPGRelationshipType
    from codegraphx.parsers.tree_sitter_parser import parse_repository
    from codegraphx.graph.cpg_builder import CPGBuilder

    repo = create_test_repo()
    try:
        ctx = IngestionContext(repo_path=repo, language=Language.PYTHON)
        ctx.ast_nodes = parse_repository(repo)

        builder = CPGBuilder()
        ctx = builder.build(ctx)

        # Test: CPG nodes created
        assert len(ctx.cpg_nodes) > 0, "Should create CPG nodes"
        cpg_labels = set(n.label for n in ctx.cpg_nodes)
        print(f"  ✓ Created {len(ctx.cpg_nodes)} CPG nodes: {[l.value for l in cpg_labels]}")

        # Test: CPG relationships created
        assert len(ctx.cpg_relationships) > 0, "Should create CPG relationships"
        cpg_rel_types = set(r.type for r in ctx.cpg_relationships)
        print(f"  ✓ Created {len(ctx.cpg_relationships)} CPG relationships: {[t.value for t in cpg_rel_types]}")

        # Test: Control flow edges exist
        flow_edges = [r for r in ctx.cpg_relationships
                      if r.type in (CPGRelationshipType.FLOWS_TO, CPGRelationshipType.BRANCHES_TO)]
        assert len(flow_edges) > 0, "Should have control flow edges"
        print(f"  ✓ Control flow edges: {len(flow_edges)}")

        # Test: Data flow edges
        data_edges = [r for r in ctx.cpg_relationships
                      if r.type in (CPGRelationshipType.DEFINES, CPGRelationshipType.DATA_DEPENDS_ON)]
        print(f"  ✓ Data flow edges: {len(data_edges)}")

        print("  ✓ Phase 3 PASSED")
        return ctx

    finally:
        shutil.rmtree(repo)


# ── Phase 4 Tests: Metrics ────────────────────────────────────────────────────

def test_phase4_metrics():
    """Phase 4 Validation: Metrics computation and risk flags."""
    print("\n═══ Phase 4: Metrics Engine ═══")

    from codegraphx.core.models import IngestionContext, Language
    from codegraphx.parsers.tree_sitter_parser import parse_repository
    from codegraphx.extractors.architecture_extractor import ArchitectureExtractor
    from codegraphx.graph.cpg_builder import CPGBuilder
    from codegraphx.metrics.metrics_engine import MetricsEngine

    repo = create_test_repo()
    try:
        ctx = IngestionContext(repo_path=repo, language=Language.PYTHON)
        ctx.ast_nodes = parse_repository(repo)

        extractor = ArchitectureExtractor()
        ctx = extractor.extract(ctx)

        cpg_builder = CPGBuilder()
        ctx = cpg_builder.build(ctx)

        engine = MetricsEngine()
        results = engine.compute_all(ctx)

        assert len(results) > 0, "Should compute metrics"
        print(f"  ✓ Computed metrics for {len(results)} nodes")

        # Check metric values are reasonable
        for node_id, metric in results.items():
            assert metric.cyclomatic_complexity >= 1, "Min complexity is 1"

        complexities = [m.cyclomatic_complexity for m in results.values()]
        print(f"  ✓ Complexity range: {min(complexities)}-{max(complexities)}")

        risk_flagged = [m for m in results.values() if m.risk_flags]
        print(f"  ✓ Risk-flagged nodes: {len(risk_flagged)}")

        print("  ✓ Phase 4 PASSED")

    finally:
        shutil.rmtree(repo)


# ── Phase 5 Tests: Semantic Layer ─────────────────────────────────────────────

def test_phase5_semantic():
    """Phase 5 Validation: Semantic enrichment and hybrid retrieval."""
    print("\n═══ Phase 5: Semantic Layer ═══")

    from codegraphx.core.models import IngestionContext, Language, NodeLabel
    from codegraphx.parsers.tree_sitter_parser import parse_repository
    from codegraphx.extractors.architecture_extractor import ArchitectureExtractor
    from codegraphx.semantic.semantic_layer import SemanticEnricher, HybridRetriever

    repo = create_test_repo()
    try:
        ctx = IngestionContext(repo_path=repo, language=Language.PYTHON)
        ctx.ast_nodes = parse_repository(repo)

        extractor = ArchitectureExtractor()
        ctx = extractor.extract(ctx)

        enricher = SemanticEnricher()
        semantic_nodes = enricher.enrich(ctx)

        assert len(semantic_nodes) > 0, "Should enrich nodes"
        print(f"  ✓ Enriched {len(semantic_nodes)} nodes")

        # Check embeddings
        has_embedding = sum(1 for s in semantic_nodes.values() if s.embedding)
        print(f"  ✓ Nodes with embeddings: {has_embedding}")

        # Check docstrings extracted
        has_docstring = sum(1 for s in semantic_nodes.values() if s.docstring)
        print(f"  ✓ Nodes with docstrings: {has_docstring}")

        # Test hybrid retrieval
        arch_nodes_dict = {n.id: n for n in ctx.arch_nodes}
        retriever = HybridRetriever(semantic_nodes, arch_nodes_dict, ctx.arch_relationships)

        results = retriever.query("process items with threshold")
        assert isinstance(results, list), "Should return list"
        print(f"  ✓ Semantic query returned {len(results)} results")

        if results:
            top = results[0]
            assert "name" in top
            assert "similarity" in top
            print(f"  ✓ Top result: {top['name']} (sim: {top['similarity']:.4f})")

        print("  ✓ Phase 5 PASSED")

    finally:
        shutil.rmtree(repo)


# ── Phase 6 Tests: LLM Interface ─────────────────────────────────────────────

def test_phase6_llm():
    """Phase 6 Validation: Query validation and prompt construction."""
    print("\n═══ Phase 6: LLM Query Interface ═══")

    from codegraphx.llm.query_interface import (
        QueryValidator, NLToCypherTranslator, SubgraphSummarizer
    )

    validator = QueryValidator()

    # Test: Valid queries pass
    result = validator.validate("MATCH (f:Function) RETURN f.name LIMIT 10")
    assert result["valid"], "Valid query should pass"
    print("  ✓ Valid query accepted")

    # Test: Forbidden clauses blocked
    result = validator.validate("MATCH (n) DELETE n")
    assert not result["valid"], "DELETE should be blocked"
    assert any("DELETE" in e for e in result["errors"])
    print("  ✓ DELETE clause blocked")

    result = validator.validate("CREATE (n:Function {name: 'hack'})")
    assert not result["valid"], "CREATE should be blocked"
    print("  ✓ CREATE clause blocked")

    result = validator.validate("MATCH (n) SET n.name = 'hack'")
    assert not result["valid"], "SET should be blocked"
    print("  ✓ SET clause blocked")

    # Test: LIMIT auto-added
    result = validator.validate("MATCH (f:Function) RETURN f.name")
    assert "LIMIT" in result["cleaned"].upper(), "Should auto-add LIMIT"
    print("  ✓ LIMIT auto-added")

    # Test: Prompt construction
    translator = NLToCypherTranslator()
    prompt = translator.build_prompt("Find all functions with high complexity")
    assert "Function" in prompt
    assert "NEVER" in prompt
    assert "CREATE" in prompt
    print("  ✓ NL→Cypher prompt constructed correctly")

    # Test: Cypher extraction from LLM response
    fake_response = "```cypher\nMATCH (f:Function) WHERE f.cyclomatic_complexity > 10 RETURN f LIMIT 20\n```"
    result = translator.translate("Find complex functions", fake_response)
    assert result["valid"], "Extracted query should be valid"
    print("  ✓ Cypher extraction from LLM response works")

    # Test: Subgraph summarizer
    summarizer = SubgraphSummarizer()
    graph = summarizer.format_result_as_json(
        nodes=[{"name": "main", "label": "Function", "fan_in": 0, "fan_out": 5}],
        relationships=[{"source": "main", "target": "helper", "type": "CALLS"}],
    )
    assert graph["stats"]["total_nodes"] == 1
    prompt = summarizer.build_summary_prompt(graph)
    assert "Entry points" in prompt
    print("  ✓ Subgraph summarization pipeline works")

    print("  ✓ Phase 6 PASSED")


# ── Phase 7 Tests: Hardening ──────────────────────────────────────────────────

def test_phase7_hardening():
    """Phase 7 Validation: Query guards, determinism, performance."""
    print("\n═══ Phase 7: Hardening & Safety ═══")

    from codegraphx.core.hardening import (
        QueryGuard, DeterminismChecker, PerformanceMonitor
    )
    from codegraphx.core.models import IngestionContext, Language

    # Test: Query guards
    guard = QueryGuard(max_nodes=100)
    query = guard.enforce_limits("MATCH (n) RETURN n")
    assert "LIMIT" in query.upper()
    print("  ✓ Query guard enforces LIMIT")

    result = guard.validate_result_size(list(range(50)))
    assert result["safe"]
    print("  ✓ Result size validation (safe)")

    result = guard.validate_result_size(list(range(100)))
    assert result["truncated"]
    print("  ✓ Result size validation (truncated)")

    # Test: Determinism
    ctx1 = IngestionContext(repo_path="/test", language=Language.PYTHON)
    fp1 = DeterminismChecker.compute_repo_fingerprint(ctx1)
    fp2 = DeterminismChecker.compute_repo_fingerprint(ctx1)
    assert DeterminismChecker.verify_idempotency(fp1, fp2)
    print("  ✓ Determinism check: same input → same fingerprint")

    # Test: Performance monitor
    monitor = PerformanceMonitor()
    monitor.start("test_phase")
    import time
    time.sleep(0.01)
    elapsed = monitor.stop("test_phase")
    assert elapsed > 0
    report = monitor.report()
    assert "test_phase" in report
    print(f"  ✓ Performance monitoring works ({report['test_phase']})")

    print("  ✓ Phase 7 PASSED")


# ── Full Pipeline Test ────────────────────────────────────────────────────────

def test_full_pipeline():
    """End-to-end pipeline test."""
    print("\n═══ Full Pipeline Integration Test ═══")

    from codegraphx.core.pipeline import IngestionPipeline

    repo = create_test_repo()
    try:
        pipeline = IngestionPipeline()
        ctx = pipeline.ingest(repo, skip_semantic=False)

        assert len(ctx.ast_nodes) > 0
        assert len(ctx.arch_nodes) > 0
        assert len(ctx.arch_relationships) > 0
        assert len(ctx.cpg_nodes) > 0
        assert len(ctx.cpg_relationships) > 0
        print(f"  ✓ Full pipeline completed successfully")

        # Test semantic query
        results = pipeline.semantic_query("processor function")
        print(f"  ✓ Semantic query returned {len(results)} results")

        # Test metrics summary
        summary = pipeline.get_metrics_summary()
        assert summary["total_nodes_analyzed"] > 0
        print(f"  ✓ Metrics: {summary['total_nodes_analyzed']} nodes, "
              f"avg complexity {summary['avg_complexity']:.1f}")

        print("  ✓ Full Pipeline PASSED")

    finally:
        shutil.rmtree(repo)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_all_tests():
    """Run all phase tests in build order."""
    print("╔═══════════════════════════════════════════╗")
    print("║  CodeGraphX 2.0 - Test Suite              ║")
    print("╚═══════════════════════════════════════════╝")

    passed = 0
    failed = 0
    errors = []

    tests = [
        ("Phase 1: Parsing", test_phase1_parsing),
        ("Phase 2: Architecture", test_phase2_architecture),
        ("Phase 3: CPG", test_phase3_cpg),
        ("Phase 4: Metrics", test_phase4_metrics),
        ("Phase 5: Semantic", test_phase5_semantic),
        ("Phase 6: LLM", test_phase6_llm),
        ("Phase 7: Hardening", test_phase7_hardening),
        ("Full Pipeline", test_full_pipeline),
    ]

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  ✗ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")

    if errors:
        print(f"\nFailures:")
        for name, err in errors:
            print(f"  ✗ {name}: {err}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
