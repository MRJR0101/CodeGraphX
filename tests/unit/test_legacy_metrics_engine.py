from __future__ import annotations

from core.models import ArchRelationship, RelationshipType
from metrics.metrics_engine import MetricsEngine


def test_max_dependency_chain_backtracks_across_converging_branches() -> None:
    relationships = [
        ArchRelationship(source_id="A", target_id="B", type=RelationshipType.DEPENDS_ON),
        ArchRelationship(source_id="A", target_id="C", type=RelationshipType.DEPENDS_ON),
        ArchRelationship(source_id="B", target_id="A", type=RelationshipType.DEPENDS_ON),
        ArchRelationship(source_id="C", target_id="B", type=RelationshipType.DEPENDS_ON),
    ]

    depth = MetricsEngine()._max_dependency_chain("A", relationships)

    assert depth == 3
