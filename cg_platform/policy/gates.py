"""
Quality gate scaffolding for CI and deployment checks.
"""
from typing import Dict, List, Any

from ..config import platform_config
from ..contracts import QualityGateResult


class QualityPolicy:
    def evaluate(self, metrics_summary: Dict[str, Any]) -> QualityGateResult:
        violations: List[str] = []

        avg_complexity = float(metrics_summary.get("avg_complexity", 0.0))
        risk_nodes = int(metrics_summary.get("risk_flagged_nodes", 0))

        cyclic_count = 0
        for detail in metrics_summary.get("risk_details", []):
            for flag in detail.get("flags", []):
                if "CYCLIC_DEPENDENCY" in flag:
                    cyclic_count += 1

        if avg_complexity > platform_config.quality.max_avg_complexity:
            violations.append(
                f"Average complexity {avg_complexity:.2f} exceeds "
                f"{platform_config.quality.max_avg_complexity:.2f}"
            )

        if risk_nodes > platform_config.quality.max_risk_nodes:
            violations.append(
                f"Risk-flagged nodes {risk_nodes} exceed "
                f"{platform_config.quality.max_risk_nodes}"
            )

        if cyclic_count > platform_config.quality.max_cyclic_nodes:
            violations.append(
                f"Cyclic nodes {cyclic_count} exceed "
                f"{platform_config.quality.max_cyclic_nodes}"
            )

        return QualityGateResult(
            passed=len(violations) == 0,
            violations=violations,
            metrics_summary=metrics_summary,
        )
