"""
Shared fixtures for tests and examples.

Graph fixtures: pre-built KnowledgeGraph instances with specific shapes.
Config fixtures: reusable rules, DomainConfigs, contexts, and state factories.
"""
from conversation_engine.fixtures.graph_fixtures import (
    create_graph_with_gaps,
    create_graph_with_orphans,
    create_graph_complete,
    create_graph_partial_coverage,
    create_minimal_graph,
)
from conversation_engine.fixtures.config_fixtures import (
    goal_req_rule,
    req_cap_rule,
    standard_rules,
    sample_config,
    partial_config,
    make_context,
    make_service,
    minimal_state,
    make_state,
    make_service_state,
)

__all__ = [
    # Graph fixtures
    "create_graph_with_gaps",
    "create_graph_with_orphans",
    "create_graph_complete",
    "create_graph_partial_coverage",
    "create_minimal_graph",
    # Config fixtures
    "goal_req_rule",
    "req_cap_rule",
    "standard_rules",
    "sample_config",
    "partial_config",
    "make_context",
    "make_service",
    "minimal_state",
    "make_state",
    "make_service_state",
]
