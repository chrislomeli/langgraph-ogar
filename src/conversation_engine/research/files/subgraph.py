"""
Conversation engine subgraph.

This module assembles the subgraph from its nodes and exposes two things:

  build_conversation_subgraph(checkpointer, reviewer) -> CompiledGraph
      The compiled LangGraph subgraph. Call this from the parent graph
      or directly in tests/demos. The parent graph adds this as a node:

          builder.add_node("conversation", conversation_subgraph)

  conversation_subgraph_from_input(input: ConversationInput) -> ConversationState
      Converts a ConversationInput into the initial ConversationState.
      Keeps the entry contract clean — callers pass a ConversationInput,
      not a raw dict.

Node execution order per turn:
  validate → interrupt_policy → [surface_to_human | reason] → [integrate | mutate_graph] → router

Router exits:
  continue   → back to validate (next turn)
  complete   → END (natural conclusion)
  hand_off   → END (parent graph takes over)
  error      → END (unrecoverable failure)
  interrupted → END (waiting for human — LangGraph resumes on next message)
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from conversation_engine.graph.state import ConversationState, ConversationInput
from conversation_engine.graph.mutation_review import MutationReviewer, AutoApproveReviewer
from conversation_engine.graph.nodes.validate import validate_node
from conversation_engine.graph.nodes.interrupt_policy import interrupt_policy_node
from conversation_engine.graph.nodes.surface import surface_to_human_node
from conversation_engine.graph.nodes.reason import reason_node
from conversation_engine.graph.nodes.integrate import integrate_node
from conversation_engine.graph.nodes.mutate import build_mutate_node
from conversation_engine.graph.nodes.router import router_node, route


def build_conversation_subgraph(
    checkpointer: BaseCheckpointSaver,
    reviewer: MutationReviewer | None = None,
) -> any:
    """
    Build and compile the conversation engine subgraph.

    Args:
        checkpointer: Postgres or memory checkpointer — injected by caller.
                      The subgraph does not own the checkpointer.
        reviewer:     MutationReviewer implementation. Defaults to
                      AutoApproveReviewer (stub). Pass HumanReviewer
                      when the UI layer is ready.

    Returns:
        Compiled LangGraph graph ready to be invoked or added as a node
        to a parent graph.
    """
    if reviewer is None:
        reviewer = AutoApproveReviewer()

    # Build the mutate node with the injected reviewer
    mutate_node = build_mutate_node(reviewer)

    builder = StateGraph(ConversationState)

    # ── Register nodes ────────────────────────────────────────────────
    builder.add_node("validate", validate_node)
    builder.add_node("interrupt_policy", interrupt_policy_node)
    builder.add_node("surface_to_human", surface_to_human_node)
    builder.add_node("reason", reason_node)
    builder.add_node("integrate", integrate_node)
    builder.add_node("mutate_graph", mutate_node)
    builder.add_node("router", router_node)

    # ── Entry point ───────────────────────────────────────────────────
    builder.set_entry_point("validate")

    # ── Fixed edges ───────────────────────────────────────────────────
    builder.add_edge("validate", "interrupt_policy")
    builder.add_edge("surface_to_human", "integrate")
    builder.add_edge("reason", "mutate_graph")
    builder.add_edge("integrate", "router")
    builder.add_edge("mutate_graph", "router")

    # ── Conditional edges ─────────────────────────────────────────────
    # interrupt_policy decides: interrupt the human or let the agent reason
    builder.add_conditional_edges(
        "interrupt_policy",
        lambda state: "surface_to_human" if state.status == "interrupted" else "reason",
        {
            "surface_to_human": "surface_to_human",
            "reason": "reason",
        },
    )

    # router decides: loop, complete, hand_off, or error
    builder.add_conditional_edges(
        "router",
        route,
        {
            "validate": "validate",   # continue → next turn
            END: END,                 # complete / hand_off / error / interrupted
        },
    )

    return builder.compile(checkpointer=checkpointer)


def initial_state_from_input(input: ConversationInput) -> ConversationState:
    """
    Convert a ConversationInput into the initial ConversationState.

    This is the canonical entry point. Callers should never construct
    ConversationState directly from a parent graph — always go through here
    so the contract is enforced in one place.
    """
    return ConversationState(
        session_id=input.session_id,
        graph=input.initial_graph,
        rules=input.rules,
        query_patterns=input.query_patterns,
        policy=input.policy,
        system_prompt=input.system_prompt,
    )
