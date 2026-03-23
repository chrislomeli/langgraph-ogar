"""
Router node — decides what happens after each turn.

The router is pure logic: no LLM, no side effects, no mutations.
It reads ConversationState and returns a routing decision.

This is intentionally the first node with real logic because:
  - It has no LLM dependency (fast to test)
  - It enforces the exit contract (the parent graph depends on this)
  - Getting exits right early prevents hard-to-fix wiring bugs later
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END

from conversation_engine.graph.state import ConversationState

logger = logging.getLogger(__name__)

RouteTarget = Literal["validate", "__end__"]


def router_node(state: ConversationState) -> dict[str, Any]:
    """
    Evaluate current state and set the routing decision.

    Does not change status — only reads it. Status is set by the nodes
    that precede the router (interrupt_policy, reason, integrate).

    Logs the routing decision for observability.
    """
    decision = _decide(state)
    logger.info(
        "[router] turn=%d status=%s → %s",
        state.current_turn,
        state.status,
        decision,
    )
    return {}   # router does not mutate state, only routes


def route(state: ConversationState) -> RouteTarget:
    """
    Conditional edge function — returns the next node name.

    Called by LangGraph after router_node executes.
    Returns "validate" to continue the loop, END to exit.

    Exit conditions:
      complete    → natural conversation end, graph is ready
      hand_off    → parent graph should take next action
      error       → unrecoverable failure, surface to parent
      interrupted → waiting for human, LangGraph suspends here
                    (resumes on next invoke with human message)
      max_turns   → safety exit, prevents infinite loops
    """
    decision = _decide(state)
    return "validate" if decision == "continue" else END


def _decide(state: ConversationState) -> str:
    """
    Core routing logic — single source of truth for exit conditions.

    Evaluated in priority order: errors first, then exits, then continue.
    """
    # Priority 1: error — always exit
    if state.status == "error":
        logger.warning("[router] exiting on error")
        return "exit"

    # Priority 2: interrupted — suspend, resume on next human message
    if state.status == "interrupted":
        return "exit"

    # Priority 3: explicit completion or hand-off
    if state.status in ("complete", "hand_off"):
        return "exit"

    # Priority 4: turn limit safety exit
    max_turns = 50  # hard ceiling, separate from policy.max_autonomous_turns
    if state.current_turn >= max_turns:
        logger.warning("[router] max_turns=%d reached, forcing exit", max_turns)
        return "exit"

    # Default: continue the loop
    return "continue"
