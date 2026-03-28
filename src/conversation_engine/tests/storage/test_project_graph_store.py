"""
Tests for DomainConfig and ProjectStore (InMemoryProjectStore).

Coverage:
- DomainConfig: creation, frozen semantics, all-None fields, metadata
- InMemoryProjectStore: save, load, delete, list, exists, upsert, empty name
- ArchitecturalOntologyContext.from_config: round-trip from DomainConfig
"""
from __future__ import annotations

import pytest

from conversation_engine.fixtures import create_graph_complete
from conversation_engine.models.domain_config import DomainConfig
from conversation_engine.models.project_spec import ProjectSpecification, GoalSpec, RequirementSpec
from conversation_engine.storage.graph_project_store import GraphProjectStore
from conversation_engine.storage.project_facade import project_to_graph
from conversation_engine.storage.project_store import (
    InMemoryProjectStore,
    ProjectStore,
)
from conversation_engine.storage.graph import KnowledgeGraph
from conversation_engine.models.rule_node import IntegrityRule
# from conversation_engine.models.query_node import GraphQueryPattern
from conversation_engine.models.validation_quiz import ValidationQuiz, FactualQuiz
from conversation_engine.graph.architectural_context import (
    ArchitecturalOntologyContext,
)
from conversation_engine.infrastructure.llm.architectural_quiz import (
    ARCHITECTURAL_SYSTEM_PROMPT,
    ARCHITECTURAL_QUIZ,
)
from conversation_engine.models import Goal, Requirement
from conversation_engine.models.base import BaseEdge, NodeType
from conversation_engine.storage.snapshot_facade import graph_to_snapshot


# ── Helpers ──────────────────────────────────────────────────────────

def _sample_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add_node(Goal(id="g1", name="Goal 1", statement="stmt"))
    g.add_node(Requirement(id="r1", name="Req 1"))
    g.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="g1", target_id="r1"))
    return g


def _sample_rules() -> list[IntegrityRule]:
    return [
        IntegrityRule(
            id="rule-goal-req",
            name="Goal → Requirement",
            description="Every goal must have at least one requirement",
            applies_to_node_type="goal",
            rule_type="minimum_outgoing_edge_count",
            target_node_types=["requirement"],
            minimum_count=1,
            severity="high",
            failure_message_template="Goal '{subject_name}' has no requirements.",
        ),
    ]


def _sample_quiz() -> list[FactualQuiz]:
    return [
        FactualQuiz(
            question="What node types exist?",
            expected_answer="goal, requirement",
            weight=1.0,
            min_score=0.5,
        ),
    ]


def _sample_spec() -> ProjectSpecification:
    return graph_to_snapshot("test-project", create_graph_complete())


def _full_config(**overrides) -> DomainConfig:
    defaults = dict(
        project_name="test-project",
        project_spec=_sample_spec(),
        rules=_sample_rules(),
        quiz=_sample_quiz(),
        # query_patterns=[],
        system_prompt="You are a test assistant.",
        metadata={"version": "1.0"},
    )
    defaults.update(overrides)
    return DomainConfig(**defaults)



# ═════════════════════════════════════════════════════════════════════
#  InMemoryProjectStore Tests
# ═════════════════════════════════════════════════════════════════════




class TestKnowledgeGraphTransforms:

    # ── save / load ──────────────────────────────────────────────────

    def test_build_graph(self):
        store = GraphProjectStore()
        config = _full_config()
        project_graph = project_to_graph(config)
        # todo add better asserts by type

        def check_node(node_type: NodeType, expected: int):
            nodes =  project_graph.get_nodes_by_type(node_type)
            assert len(nodes) == expected



        project = project_graph.get_nodes_by_type(NodeType.PROJECT)
        goals = project_graph.get_nodes_by_type(NodeType.GOAL)
        reqs = project_graph.get_nodes_by_type(NodeType.REQUIREMENT)
        capabilities = project_graph.get_nodes_by_type(NodeType.CAPABILITY)
        components = project_graph.get_nodes_by_type(NodeType.COMPONENT)
        rules = project_graph.get_nodes_by_type(NodeType.RULE)

        assert len(project) == 1
        assert len(goals) == 2
        assert len(reqs) == 2
        assert len(capabilities) == 2
        assert len(components) == 2
        assert len(rules) == 1
