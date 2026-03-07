"""
Graph builder — M7: Persistence — Save and Load.

The parent graph now has 6 routes:
  START → intent_router → conditional → creation subgraph → END
                                      → save_project → END
                                      → load_project → END
                                      → list_projects → END
                                      → answerer → END

KEY CONCEPTS:
  - MusicStore is INJECTED via build_music_graph(store=...).
  - Persistence nodes are created via factories: make_save_project(store).
  - The graph builder doesn't know which store implementation is used.
  - SqliteSaver checkpointer enables durable interrupt/resume (optional).
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ParentState
from .store import MusicStore, InMemoryStore
from .nodes.intent_router import intent_router, route_by_intent
from .nodes.answerer import answerer
from .nodes.save_project import make_save_project
from .nodes.load_project import make_load_project
from .nodes.list_projects import make_list_projects
from .subgraphs import build_creation_subgraph


def build_music_graph(
    store: MusicStore | None = None,
    checkpointer=None,
):
    """Build the M7 parent graph with persistence.

    Args:
        store: MusicStore implementation. Defaults to InMemoryStore.
        checkpointer: LangGraph checkpointer. Defaults to MemorySaver.
    """
    if store is None:
        store = InMemoryStore()
    if checkpointer is None:
        checkpointer = MemorySaver()

    builder = StateGraph(ParentState)

    creation_subgraph = build_creation_subgraph()

    # Parent nodes
    builder.add_node("intent_router", intent_router)
    builder.add_node("creation", creation_subgraph)
    builder.add_node("save_project", make_save_project(store))
    builder.add_node("load_project", make_load_project(store))
    builder.add_node("list_projects", make_list_projects(store))
    builder.add_node("answerer", answerer)

    # Edges
    builder.add_edge(START, "intent_router")
    builder.add_conditional_edges("intent_router", route_by_intent)
    builder.add_edge("creation", END)
    builder.add_edge("save_project", END)
    builder.add_edge("load_project", END)
    builder.add_edge("list_projects", END)
    builder.add_edge("answerer", END)

    return builder.compile(checkpointer=checkpointer)
