"""
Graph builder — M6: Wire in the Real Tools.

The parent graph structure is identical to M5:
  START → intent_router → conditional → creation subgraph → END
                                      → answerer → END

The creation subgraph now uses real tools:
  START → sketch_parser → engine → compiler → renderer → presenter → END

KEY CONCEPT: The graph structure didn't change from M5.
Only the node implementations changed. This is the payoff of
designing the graph first and implementing tools second.
"""

from langgraph.graph import StateGraph, START, END

from .state import ParentState
from .nodes import intent_router, route_by_intent, answerer
from .subgraphs import build_creation_subgraph


def build_music_graph():
    """Build the M6 parent graph with real-tool creation subgraph."""
    builder = StateGraph(ParentState)

    creation_subgraph = build_creation_subgraph()

    builder.add_node("intent_router", intent_router)
    builder.add_node("creation", creation_subgraph)
    builder.add_node("answerer", answerer)

    builder.add_edge(START, "intent_router")
    builder.add_conditional_edges("intent_router", route_by_intent)
    builder.add_edge("creation", END)
    builder.add_edge("answerer", END)

    return builder.compile()
