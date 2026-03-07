"""
Graph builder -- M11: PlanOrchestrator Integration.

KEY CONCEPT: The creation and refinement subgraphs now use
PlanOrchestrator to drive their pipelines as DAGs. The parent
graph topology is unchanged -- the innovation is inside the subgraphs.

Before (M10):
  - Subgraphs are linear chains of nodes calling tools via registry
  - No DAG lifecycle management

After (M11):
  - Creation subgraph builds a PlanGraph DAG and runs PlanOrchestrator
  - Refinement subgraph reuses PlanGraph, applies refinement, re-executes
  - Orchestrator events provide observability into the DAG lifecycle
  - ScopeRegistry maps scope_type to domain planners + executors
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ParentState
from .store import MusicStore, InMemoryStore
from .domain_executors import build_scope_registry
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
    """Build the M11 parent graph with PlanOrchestrator-driven subgraphs.

    Args:
        store: MusicStore implementation. Defaults to InMemoryStore.
        checkpointer: LangGraph checkpointer. Defaults to MemorySaver.
    """
    if store is None:
        store = InMemoryStore()
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Build scope registry for orchestrator
    scope_registry = build_scope_registry()

    # Build subgraphs with orchestrator
    creation_subgraph = build_creation_subgraph(scope_registry)
    refinement_subgraph = build_refinement_subgraph(scope_registry)

    # Parent graph
    builder = StateGraph(ParentState)

    builder.add_node("intent_router", intent_router)
    builder.add_node("creation", creation_subgraph)
    builder.add_node("refinement", refinement_subgraph)
    builder.add_node("save_project", make_save_project(store))
    builder.add_node("load_project", make_load_project(store))
    builder.add_node("list_projects", make_list_projects(store))
    builder.add_node("answerer", answerer)

    builder.add_edge(START, "intent_router")
    builder.add_conditional_edges("intent_router", route_by_intent)
    builder.add_edge("creation", END)
    builder.add_edge("refinement", END)
    builder.add_edge("save_project", END)
    builder.add_edge("load_project", END)
    builder.add_edge("list_projects", END)
    builder.add_edge("answerer", END)

    return builder.compile(checkpointer=checkpointer)
