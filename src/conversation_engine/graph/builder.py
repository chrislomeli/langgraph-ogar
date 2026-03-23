"""
Conversation subgraph builder.

Topology:
    START → preflight → route → validate → reason → respond → route
    route_after_preflight → validate   (if preflight passes or was skipped)
    route_after_preflight → END        (if preflight fails → status='error')
    route_after_respond   → validate   (if open findings remain and turns < max)
    route_after_respond   → END        (complete, or max turns reached)

The graph is **domain-agnostic**.  It works with Findings (not
Assessments) and delegates all domain logic to the injected
ConversationContext.

The graph is designed to be used standalone or as a subgraph of a
larger application.  It does NOT own the checkpointer or LLM client.

Infrastructure:
- InstrumentedGraph wraps every node with a composable NodeMiddleware chain
- Cross-cutting concerns (logging, metrics, error handling, retry, circuit
  breaker, config) are injected via node_middleware, not baked into topology
- Pre-flight LLM validation is a first-class node, not imperative build code
"""
from __future__ import annotations

import logging
from typing import Literal, Optional, Sequence

from langgraph.graph import START, END

from conversation_engine.graph.state import ConversationState
from conversation_engine.graph.nodes import preflight, validate, reason, respond
from conversation_engine.infrastructure.instrumented_graph import (
    InstrumentedGraph,
    Interceptor,
    Middleware,
)
from conversation_engine.infrastructure.middleware.base import NodeMiddleware

logger = logging.getLogger(__name__)


MAX_TURNS = 5


# ── Routers ──────────────────────────────────────────────────────────

def route_after_preflight(state: ConversationState) -> Literal["validate", "__end__"]:
    """
    After preflight: continue to validate if OK, exit if error.
    """
    if state.get("status") == "error":
        return "__end__"
    return "validate"


def route_after_respond(state: ConversationState) -> Literal["validate", "__end__"]:
    """
    Decide whether to loop back for another validation pass or finish.

    Exits when:
    - No open findings remain     →  "complete"
    - Max turns reached           →  "max_turns"
    - Status set to error/hand_off by a node  →  exit
    """
    status = state.get("status", "running")
    if status in ("complete", "error", "hand_off"):
        return "__end__"

    current_turn = state.get("current_turn", 0)
    if current_turn >= MAX_TURNS:
        return "__end__"

    open_findings = [f for f in state.get("findings", []) if not f.resolved]
    if not open_findings:
        return "__end__"

    return "validate"


# ── Builder ──────────────────────────────────────────────────────────

def build_conversation_graph(
    *,
    node_middleware: Sequence[NodeMiddleware] | None = None,
    # Legacy parameters — deprecated, kept for backwards compatibility
    interceptors: Sequence[Interceptor] | None = None,
    middleware: Sequence[Middleware] | None = None,
):
    """
    Build and compile the conversation subgraph.

    Parameters
    ----------
    node_middleware : Sequence[NodeMiddleware], optional
        Composable cross-cutting concerns applied to every node.
        Order matters: first in list = outermost wrapper.
        Typical order: Logging → Metrics → ErrorHandling → Retry → [node]
    interceptors : Sequence[Interceptor], optional
        DEPRECATED. Use node_middleware instead.
    middleware : Sequence[Middleware], optional
        DEPRECATED. Use node_middleware instead.

    Returns a compiled graph ready for .invoke() or .stream().

    Pre-flight validation:
        The preflight node pulls the quiz and system prompt from the
        ConversationContext, and the LLM from state["llm"].  If either
        is absent, preflight passes through immediately.  On failure,
        it sets status='error' and the router exits the graph.
    """
    builder = InstrumentedGraph(
        ConversationState,
        node_middleware=node_middleware,
        interceptors=interceptors,
        middleware=middleware,
    )

    # Nodes
    builder.add_node("preflight", preflight)
    builder.add_node("validate", validate)
    builder.add_node("reason", reason)
    builder.add_node("respond", respond)

    # Edges
    builder.add_edge(START, "preflight")
    builder.add_conditional_edges("preflight", route_after_preflight)
    builder.add_edge("validate", "reason")
    builder.add_edge("reason", "respond")
    builder.add_conditional_edges("respond", route_after_respond)

    return builder.compile()
