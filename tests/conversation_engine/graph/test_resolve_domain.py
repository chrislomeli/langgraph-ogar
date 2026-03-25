"""
Tests for the resolve_domain graph node and route_after_resolve_domain router.

Coverage:
- Scenario 1: context already provided → pass through
- Scenario 2a: project_name + store → load and build context
- Scenario 2b: project_name + store, project not found → error
- Scenario 3: no project_name, human provides one → needs_project_name
- Fallback: no context, no name, no human → error
- Router: running → preflight, needs_project_name → resolve_domain, error → __end__
"""
from __future__ import annotations

import pytest

from conversation_engine.graph.nodes import resolve_domain
from conversation_engine.graph.builder import route_after_resolve_domain
from conversation_engine.graph.architectural_context import (
    ArchitecturalOntologyContext,
)
from conversation_engine.models.domain_config import DomainConfig
from conversation_engine.storage.project_store import InMemoryProjectStore
from conversation_engine.storage.graph import KnowledgeGraph
from conversation_engine.models.rules import IntegrityRule
from conversation_engine.models import Goal, Requirement
from conversation_engine.models.base import BaseEdge
from conversation_engine.infrastructure.human import (
    HumanRequest,
    HumanResponse,
    MockHuman,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _sample_config() -> DomainConfig:
    g = KnowledgeGraph()
    g.add_node(Goal(id="g1", name="Goal 1", statement="A goal"))
    g.add_node(Requirement(id="r1", name="Req 1"))
    g.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="g1", target_id="r1"))
    return DomainConfig(
        project_name="test-project",
        knowledge_graph=g,
        rules=[
            IntegrityRule(
                id="rule-goal-req",
                name="Goal → Requirement",
                description="Every goal must have at least one requirement",
                applies_to_node_type="goal",
                rule_type="minimum_outgoing_edge_count",
                edge_type="SATISFIED_BY",
                target_node_types=["requirement"],
                minimum_count=1,
                severity="high",
                failure_message_template="Goal '{subject_name}' has no requirements.",
            ),
        ],
        system_prompt="Test system prompt.",
    )


def _minimal_state(**overrides) -> dict:
    """Build a minimal ConversationState dict with sensible defaults."""
    state = {
        "context": None,
        "session_id": "test-session",
        "project_name": None,
        "project_store": None,
        "llm": None,
        "human": None,
        "tool_client": None,
        "findings": [],
        "messages": [],
        "current_turn": 0,
        "status": "running",
        "node_result": None,
        "preflight_passed": False,
    }
    state.update(overrides)
    return state


# ═════════════════════════════════════════════════════════════════════
#  resolve_domain node
# ═════════════════════════════════════════════════════════════════════

class TestResolveDomainPassThrough:
    """Scenario 1: context already provided."""

    def test_context_set_returns_running(self):
        config = _sample_config()
        ctx = ArchitecturalOntologyContext(config)
        state = _minimal_state(context=ctx)
        result = resolve_domain(state)
        assert result["status"] == "running"
        assert "context" not in result  # no change needed

    def test_context_set_does_not_overwrite(self):
        config = _sample_config()
        ctx = ArchitecturalOntologyContext(config)
        state = _minimal_state(context=ctx, project_name="other", project_store=InMemoryProjectStore())
        result = resolve_domain(state)
        assert result["status"] == "running"
        assert "context" not in result


class TestResolveDomainFromStore:
    """Scenario 2: load from store by project_name."""

    def test_load_existing_project(self):
        store = InMemoryProjectStore()
        config = _sample_config()
        store.save(config)

        state = _minimal_state(project_name="test-project", project_store=store)
        result = resolve_domain(state)

        assert result["status"] == "running"
        assert "context" in result
        ctx = result["context"]
        assert isinstance(ctx, ArchitecturalOntologyContext)
        assert ctx.graph.node_count() == 2
        assert len(ctx.rules) == 1
        assert ctx.system_prompt == "Test system prompt."

    def test_project_not_found_returns_error(self):
        store = InMemoryProjectStore()
        state = _minimal_state(project_name="nonexistent", project_store=store)
        result = resolve_domain(state)

        assert result["status"] == "error"
        assert len(result["messages"]) == 1
        assert "not found" in result["messages"][0].content


class TestResolveDomainAskHuman:
    """Scenario 3: ask human for project name."""

    def test_human_provides_name(self):
        human = MockHuman(responses=["my-project"])
        state = _minimal_state(human=human)
        result = resolve_domain(state)

        assert result["status"] == "needs_project_name"
        assert result["project_name"] == "my-project"

    def test_human_provides_name_with_whitespace(self):
        human = MockHuman(responses=["  padded-name  "])
        state = _minimal_state(human=human)
        result = resolve_domain(state)

        assert result["project_name"] == "padded-name"


class TestResolveDomainFallback:
    """Fallback: nothing to work with."""

    def test_no_context_no_name_no_human(self):
        state = _minimal_state()
        result = resolve_domain(state)
        assert result["status"] == "error"
        assert "Cannot start" in result["messages"][0].content

    def test_no_context_no_name_no_store(self):
        state = _minimal_state(project_name="test-project")
        result = resolve_domain(state)
        assert result["status"] == "error"


# ═════════════════════════════════════════════════════════════════════
#  route_after_resolve_domain
# ═════════════════════════════════════════════════════════════════════

class TestRouteAfterResolveDomain:

    def test_running_goes_to_preflight(self):
        assert route_after_resolve_domain({"status": "running"}) == "preflight"

    def test_needs_project_name_loops_back(self):
        assert route_after_resolve_domain({"status": "needs_project_name"}) == "resolve_domain"

    def test_error_goes_to_end(self):
        assert route_after_resolve_domain({"status": "error"}) == "__end__"

    def test_default_status_goes_to_preflight(self):
        assert route_after_resolve_domain({}) == "preflight"


# ═════════════════════════════════════════════════════════════════════
#  Integration: resolve_domain → router → preflight chain
# ═════════════════════════════════════════════════════════════════════

class TestResolveDomainIntegration:
    """Simulate the resolve → route → resolve loop for scenario 3."""

    def test_human_name_then_store_load(self):
        store = InMemoryProjectStore()
        store.save(_sample_config())
        human = MockHuman(responses=["test-project"])

        # Turn 1: no project_name, human provides one
        state = _minimal_state(project_store=store, human=human)
        result1 = resolve_domain(state)
        assert result1["status"] == "needs_project_name"
        assert result1["project_name"] == "test-project"

        route1 = route_after_resolve_domain(result1)
        assert route1 == "resolve_domain"

        # Turn 2: project_name now set, load from store
        state.update(result1)
        result2 = resolve_domain(state)
        assert result2["status"] == "running"
        assert isinstance(result2["context"], ArchitecturalOntologyContext)

        route2 = route_after_resolve_domain(result2)
        assert route2 == "preflight"
