"""
CodeGraphX 2.0 - Hardening & Safety (Phase 7)
Query guards, determinism checks, and performance monitoring.
"""
import time
import hashlib
import json
from typing import Dict, Any, Callable
from functools import wraps

from codegraphx.core.config import config
from codegraphx.core.models import IngestionContext


# ── Query Guards (Phase 7.1) ──────────────────────────────────────────────────

class QueryGuard:
    """Enforces safety limits on graph queries."""

    def __init__(self, max_nodes: int = 1000, timeout_seconds: int = 30):
        self.max_nodes = max_nodes or config.llm.max_result_nodes
        self.timeout_seconds = timeout_seconds or config.llm.query_timeout_seconds

    def enforce_limits(self, cypher: str) -> str:
        """Add LIMIT and timeout hints to Cypher query.

        Args:
            cypher: Raw Cypher query.

        Returns:
            Query with enforced limits.
        """
        upper = cypher.upper()

        # Enforce LIMIT
        if "LIMIT" not in upper:
            cypher = cypher.rstrip().rstrip(";") + f" LIMIT {self.max_nodes}"

        return cypher

    def validate_result_size(self, result: list) -> Dict[str, Any]:
        """Check if query result is within safe bounds.

        Args:
            result: Query result list.

        Returns:
            Dict with 'safe', 'count', 'truncated' fields.
        """
        count = len(result)
        truncated = count >= self.max_nodes

        return {
            "safe": count <= self.max_nodes,
            "count": count,
            "truncated": truncated,
            "message": f"Result truncated to {self.max_nodes} nodes" if truncated else "OK",
        }


# ── Determinism Checks (Phase 7.2) ───────────────────────────────────────────

class DeterminismChecker:
    """Ensures same repo → same graph. Idempotent ingestion."""

    @staticmethod
    def compute_repo_fingerprint(ctx: IngestionContext) -> str:
        """Compute a deterministic fingerprint for the ingestion result.

        Args:
            ctx: Completed IngestionContext.

        Returns:
            SHA-256 hex digest representing the graph state.
        """
        # Sort nodes and relationships deterministically
        node_data = sorted(
            [(n.label.value if hasattr(n.label, 'value') else str(n.label), n.name, n.file_path)
             for n in ctx.arch_nodes]
        )

        rel_data = sorted(
            [(r.source_id, r.target_id, r.type.value if hasattr(r.type, 'value') else str(r.type))
             for r in ctx.arch_relationships]
        )

        fingerprint_input = json.dumps({
            "nodes": node_data,
            "relationships": rel_data,
            "node_count": len(ctx.arch_nodes),
            "rel_count": len(ctx.arch_relationships),
        }, sort_keys=True)

        return hashlib.sha256(fingerprint_input.encode()).hexdigest()

    @staticmethod
    def verify_idempotency(fingerprint1: str, fingerprint2: str) -> bool:
        """Verify two ingestion runs produce identical results.

        Args:
            fingerprint1: First run fingerprint.
            fingerprint2: Second run fingerprint.

        Returns:
            True if identical.
        """
        return fingerprint1 == fingerprint2


# ── Performance Monitoring (Phase 7.3) ────────────────────────────────────────

class PerformanceMonitor:
    """Tracks ingestion and query performance."""

    def __init__(self):
        self.timings: Dict[str, float] = {}
        self._start_times: Dict[str, float] = {}

    def start(self, label: str):
        """Start timing a phase."""
        self._start_times[label] = time.time()

    def stop(self, label: str) -> float:
        """Stop timing and return elapsed seconds."""
        if label not in self._start_times:
            return 0.0
        elapsed = time.time() - self._start_times[label]
        self.timings[label] = elapsed
        del self._start_times[label]
        return elapsed

    def report(self) -> Dict[str, str]:
        """Generate performance report.

        Returns:
            Dict of phase -> formatted time string.
        """
        report = {}
        for label, elapsed in self.timings.items():
            if elapsed < 1.0:
                report[label] = f"{elapsed*1000:.1f}ms"
            elif elapsed < 60:
                report[label] = f"{elapsed:.2f}s"
            else:
                minutes = int(elapsed // 60)
                seconds = elapsed % 60
                report[label] = f"{minutes}m {seconds:.1f}s"
        return report

    def check_performance_goals(self) -> Dict[str, bool]:
        """Check against Phase 7.3 performance goals.

        Goals:
        - Ingest 100k LOC under 3 minutes
        - Query under 500ms for common metrics
        """
        goals = {}

        if "ingestion" in self.timings:
            goals["ingest_under_3min"] = self.timings["ingestion"] < 180.0

        query_phases = [k for k in self.timings if "query" in k.lower()]
        for qp in query_phases:
            goals[f"{qp}_under_500ms"] = self.timings[qp] < 0.5

        return goals


def timed(label: str):
    """Decorator to time a function execution."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            print(f"[PERF] {label}: {elapsed:.3f}s")
            return result
        return wrapper
    return decorator
