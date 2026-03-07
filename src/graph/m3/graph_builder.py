"""
Graph builder — M3: Human-in-the-loop.

The graph:
  START → mock_planner → plan_review → conditional → ...
                ↑         (interrupt()        │
                │          pauses here)        │
                │     approved → stub_compiler │
                └──── rejected ───────────────┘
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .nodes import mock_planner, plan_review
from .state import MusicGraphState


def on_approval(state: MusicGraphState) -> dict:
    """Placeholder for the real compiler. Just marks that compilation happened."""
    return {"score_generated": True}


def route_after_review(state: MusicGraphState) -> str:
    """Conditional edge: approved → compiler, rejected → back to engine."""
    if state.get("approved"):
        return "on_approval"
    return "mock_planner"


def build_music_graph():
    """Build the M3 graph with MemorySaver checkpointer for interrupt/resume."""
    builder = StateGraph(MusicGraphState)

    builder.add_node("mock_planner", mock_planner)
    builder.add_node("plan_review", plan_review)
    builder.add_node("on_approval", on_approval)

    builder.add_edge(START, "mock_planner")
    builder.add_edge("mock_planner", "plan_review")
    builder.add_conditional_edges("plan_review", route_after_review)
    builder.add_edge("on_approval", END)

    return builder.compile(checkpointer=MemorySaver())