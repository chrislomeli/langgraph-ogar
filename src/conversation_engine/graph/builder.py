"""
Conversation subgraph builder.

Topology:
    START → validate → reason → respond → route
    route → validate   (if open findings remain and turns < max)
    route → END        (complete, or max turns reached)

The graph is **domain-agnostic**.  It works with Findings (not
Assessments) and delegates all domain logic to the injected
ConversationContext.

The graph is designed to be used standalone or as a subgraph of a
larger application.  It does NOT own the checkpointer or LLM client.

Infrastructure:
- InstrumentedGraph wraps every node with a composable NodeMiddleware chain
- Cross-cutting concerns (logging, metrics, error handling, retry, circuit
  breaker, config) are injected via node_middleware, not baked into topology
"""
from __future__ import annotations

import logging
from typing import List, Literal, Optional, Sequence

from langgraph.graph import START, END

from conversation_engine.graph.state import ConversationState
from conversation_engine.graph.nodes import validate, reason, respond
from conversation_engine.infrastructure.instrumented_graph import (
    InstrumentedGraph,
    Interceptor,
    Middleware,
)
from conversation_engine.infrastructure.middleware.base import NodeMiddleware
from conversation_engine.infrastructure.llm import (
    CallLLM,
    LLMValidator,
    LLMValidatorReport,
    ValidationQuiz,
    quiz_report_summary,
)

logger = logging.getLogger(__name__)


MAX_TURNS = 5


# ── Conversation router ─────────────────────────────────────────────

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

class LLMPreflightError(RuntimeError):
    """Raised when the LLM fails pre-run validation."""

    def __init__(self, report: LLMValidatorReport):
        self.report = report
        super().__init__(
            f"LLM failed pre-run validation "
            f"(score={report.weighted_score:.1%}, "
            f"threshold={report.pass_threshold:.1%})"
        )


def build_conversation_graph(
    *,
    node_middleware: Sequence[NodeMiddleware] | None = None,
    # Legacy parameters — deprecated, kept for backwards compatibility
    interceptors: Sequence[Interceptor] | None = None,
    middleware: Sequence[Middleware] | None = None,
    # LLM pre-flight validation
    llm: Optional[CallLLM] = None,
    preflight_quiz: Optional[List[ValidationQuiz]] = None,
    preflight_system_prompt: Optional[str] = None,
    preflight_threshold: float = 0.7,
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
    llm : CallLLM, optional
        LLM callable to use in the conversation loop.
        If provided with preflight_quiz, the LLM is validated before building.
    preflight_quiz : list[ValidationQuiz], optional
        Quiz questions for pre-run LLM validation.
        Only runs if both llm and preflight_quiz are provided.
    preflight_system_prompt : str, optional
        System prompt for the pre-run validator.
    preflight_threshold : float
        Minimum weighted score to pass validation (default 0.7).

    Returns a compiled graph ready for .invoke() or .stream().

    Raises
    ------
    LLMPreflightError
        If the LLM fails pre-run validation.
    """
    # ── Pre-flight LLM validation ────────────────────────────────────
    if llm is not None and preflight_quiz is not None:
        validator = LLMValidator(
            llm=llm,
            system_prompt=preflight_system_prompt or "",
            quiz=preflight_quiz,
            pass_threshold=preflight_threshold,
        )
        report = validator.run()
        if not report.passed:
            logger.error(
                "LLM pre-flight validation failed:\n%s",
                quiz_report_summary(report),
            )
            raise LLMPreflightError(report)
        logger.info(
            "LLM pre-flight validation passed (score=%.1f%%)",
            report.weighted_score * 100,
        )

    # ── Build graph ──────────────────────────────────────────────────
    builder = InstrumentedGraph(
        ConversationState,
        node_middleware=node_middleware,
        interceptors=interceptors,
        middleware=middleware,
    )

    # Nodes
    builder.add_node("validate", validate)
    builder.add_node("reason", reason)
    builder.add_node("respond", respond)

    # Edges — clean topology, no error-routing boilerplate
    # Error handling is now a middleware concern, not a graph topology concern
    builder.add_edge(START, "validate")
    builder.add_edge("validate", "reason")
    builder.add_edge("reason", "respond")
    builder.add_conditional_edges("respond", route_after_respond)

    return builder.compile()
