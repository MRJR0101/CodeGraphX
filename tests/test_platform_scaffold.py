import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from codegraphx.cg_platform.runtime import build_runtime
    from codegraphx.cg_platform.policy.gates import QualityPolicy
except ModuleNotFoundError:
    try:
        from cg_platform.runtime import build_runtime
        from cg_platform.policy.gates import QualityPolicy
    except ModuleNotFoundError:
        build_runtime = None
        QualityPolicy = None


class TestPlatformScaffold(unittest.TestCase):
    @unittest.skipIf(build_runtime is None, "platform scaffold is unavailable in this package layout")
    def test_runtime_wires_services(self):
        runtime = build_runtime()
        self.assertIsNotNone(runtime.ingestion_service)
        self.assertIsNotNone(runtime.query_service)
        self.assertIsNotNone(runtime.ingestion_repository)

    @unittest.skipIf(QualityPolicy is None, "platform scaffold is unavailable in this package layout")
    def test_quality_policy_evaluates_thresholds(self):
        policy = QualityPolicy()
        result = policy.evaluate(
            {
                "avg_complexity": 50,
                "risk_flagged_nodes": 100,
                "risk_details": [{"flags": ["CYCLIC_DEPENDENCY"]}] * 30,
            }
        )
        self.assertFalse(result.passed)
        self.assertGreaterEqual(len(result.violations), 1)


if __name__ == "__main__":
    unittest.main()
