"""
Graph builder — M10: InstrumentedGraph + StateMediator.

KEY CONCEPT: The creation and refinement subgraphs use InstrumentedGraph
with interceptor hooks (logging, metrics) and StateMediator middleware.
Every tool-calling node in the subgraphs gets automatic observability.

The parent graph uses plain StateGraph because it contains compiled
subgraph nodes (which can't be wrapped by functools.wraps). Persistence
nodes in the parent use the M9 pattern (registry handler direct calls)
since they're simple enough not to need mediation.

Before (M9):
  - Plain StateGraph everywhere, no observability

After (M10):
  - Subgraphs use InstrumentedGraph with interceptors + StateMediator
  - Nodes in subgraphs return ToolResultEnvelope → StateMediator → state patches
  - Shared MetricsInterceptor collects timing data across all subgraph nodes
  - Parent graph uses StateGraph (compiled subgraphs can't be wrapped)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from framework.langgraph_ext.tool_client.client import LocalToolClient
from framework.langgraph_ext.interceptors.logging_interceptor import LoggingInterceptor
from framework.langgraph_ext.interceptors.metrics_interceptor import MetricsInterceptor

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
    metrics_interceptor: MetricsInterceptor | None = None,
):
    """Build the M10 parent graph with instrumented subgraphs.

    Args:
        store: MusicStore implementation. Defaults to InMemoryStore.
        checkpointer: LangGraph checkpointer. Defaults to MemorySaver.
        metrics_interceptor: Optional shared MetricsInterceptor for collecting
            timing data. If None, one is created automatically.

    Returns:
        Tuple of (compiled_graph, metrics_interceptor) so callers can
        inspect metrics after invocation.
    """
    if store is None:
        store = InMemoryStore()
    if checkpointer is None:
        checkpointer = MemorySaver()
    if metrics_interceptor is None:
        metrics_interceptor = MetricsInterceptor()

    # Build registry and client
    registry = build_tool_registry(store=store)
    tool_client = LocalToolClient(registry)

    # Shared interceptors for subgraphs
    logging_interceptor = LoggingInterceptor()

    # Build subgraphs with InstrumentedGraph + shared interceptors
    creation_subgraph = build_creation_subgraph(
        tool_client,
        logging_interceptor=logging_interceptor,
        metrics_interceptor=metrics_interceptor,
    )
    refinement_subgraph = build_refinement_subgraph(
        tool_client,
        logging_interceptor=logging_interceptor,
        metrics_interceptor=metrics_interceptor,
    )

    # Parent graph — plain StateGraph (compiled subgraphs can't be wrapped)
    # Persistence nodes use M9 pattern (registry handler direct calls)
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

    app = builder.compile(checkpointer=checkpointer)
    return app, metrics_interceptor
