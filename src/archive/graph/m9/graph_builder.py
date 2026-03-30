"""
Graph builder — M9: ToolSpec + Registry.

KEY CONCEPT: The graph builder now creates a ToolRegistry + LocalToolClient
and injects the client into subgraphs and persistence nodes. The graph
topology is identical to M8 — the innovation is in how nodes call tools.

Before (M8):
  - Nodes call domain logic directly: _planner.plan(sketch)
  - Persistence nodes get a MusicStore via HOF

After (M9):
  - All tools registered in a ToolRegistry
  - LocalToolClient validates inputs/outputs, wraps in ToolResultEnvelope
  - Nodes call tool_client.call("tool_name", args)
  - Every call gets provenance metadata (timing, input hash, success/failure)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from framework.langgraph_ext.tool_client.client import LocalToolClient

from .state import ParentState
from .store import MusicStore, InMemoryStore
from .tool_defs import build_tool_registry
from .nodes.intent_router import intent_router, route_by_intent
from .nodes.answerer import answerer
from .nodes.save_project import make_save_project
from .nodes.load_project import make_load_project
from .nodes.list_projects import make_list_projects
from .subgraphs import build_creation_subgraph, build_refinement_subgraph


def build_music_graph(
    store: MusicStore | None = None,
    checkpointer=None,
):
    """Build the M9 parent graph with tool-client-backed nodes.

    Args:
        store: MusicStore implementation. Defaults to InMemoryStore.
        checkpointer: LangGraph checkpointer. Defaults to MemorySaver.
    """
    if store is None:
        store = InMemoryStore()
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Build registry and client — the M9 innovation
    registry = build_tool_registry(store=store)
    tool_client = LocalToolClient(registry)

    # Build subgraphs with tool client injected
    creation_subgraph = build_creation_subgraph(tool_client)
    refinement_subgraph = build_refinement_subgraph(tool_client)

    # Parent nodes
    builder = StateGraph(ParentState)

    builder.add_node("intent_router", intent_router)
    builder.add_node("creation", creation_subgraph)
    builder.add_node("refinement", refinement_subgraph)
    builder.add_node("save_project", make_save_project(tool_client))
    builder.add_node("load_project", make_load_project(tool_client))
    builder.add_node("list_projects", make_list_projects(tool_client))
    builder.add_node("answerer", answerer)

    # Edges
    builder.add_edge(START, "intent_router")
    builder.add_conditional_edges("intent_router", route_by_intent)
    builder.add_edge("creation", END)
    builder.add_edge("refinement", END)
    builder.add_edge("save_project", END)
    builder.add_edge("load_project", END)
    builder.add_edge("list_projects", END)
    builder.add_edge("answerer", END)

    return builder.compile(checkpointer=checkpointer)
