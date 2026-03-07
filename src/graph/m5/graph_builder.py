"""
Graph builder — M5: Subgraphs.

The parent graph:
  START → intent_router → conditional → creation subgraph → END
                                      → answerer → END

KEY CONCEPTS:
  - A compiled subgraph is added as a node with add_node().
  - LangGraph handles state mapping automatically — overlapping field
    names between ParentState and CreationState are copied in/out.
  - The subgraph runs its entire internal pipeline as if it were
    a single node from the parent's perspective.
  - The subgraph is independently testable — you can compile and
    invoke it on its own.
"""

from langgraph.graph import StateGraph, START, END

from .state import ParentState
from .nodes import intent_router, route_by_intent, answerer
from .subgraphs import build_creation_subgraph


def build_music_graph():
    """Build the M5 parent graph with a creation subgraph."""
    builder = StateGraph(ParentState)

    # Compile the creation subgraph
    creation_subgraph = build_creation_subgraph()

    # Parent nodes
    builder.add_node("intent_router", intent_router)
    builder.add_node("creation", creation_subgraph)  # ← Subgraph as a node!
    builder.add_node("answerer", answerer)

    # Edges
    builder.add_edge(START, "intent_router")
    builder.add_conditional_edges("intent_router", route_by_intent)
    builder.add_edge("creation", END)
    builder.add_edge("answerer", END)

    return builder.compile()
