"""
Graph builder -- M12: Prompt Templates + LLM Swap.

KEY CONCEPT: The graph builder now accepts a PlannerStrategy parameter.
This is the single swap point: change the strategy and the entire pipeline
uses a different planning backend.

  build_music_graph(strategy=DeterministicStrategy())   # rule-based
  build_music_graph(strategy=LLMStrategy("gpt-4"))      # LLM-backed (stub)
  build_music_graph(strategy=FallbackStrategy(llm, det)) # production pattern
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ParentState
from .store import MusicStore, InMemoryStore
from .domain_executors import build_scope_registry
from .planner_strategy import PlannerStrategy, DeterministicStrategy
from .nodes.intent_router import intent_router, route_by_intent
from .nodes.answerer import answerer
from .nodes.save_project import make_save_project
from .nodes.load_project import make_load_project
from .nodes.list_projects import make_list_projects
from .subgraphs import build_creation_subgraph, build_refinement_subgraph


def build_music_graph(
    store: MusicStore | None = None,
    checkpointer=None,
    strategy: PlannerStrategy | None = None,
):
    """Build the M12 parent graph with pluggable engine strategy.

    Args:
        store: MusicStore implementation. Defaults to InMemoryStore.
        checkpointer: LangGraph checkpointer. Defaults to MemorySaver.
        strategy: PlannerStrategy for plan generation.
                  Defaults to DeterministicStrategy.
    """
    if store is None:
        store = InMemoryStore()
    if checkpointer is None:
        checkpointer = MemorySaver()
    if strategy is None:
        strategy = DeterministicStrategy()

    scope_registry = build_scope_registry(strategy=strategy)

    creation_subgraph = build_creation_subgraph(strategy=strategy, scope_registry=scope_registry)
    refinement_subgraph = build_refinement_subgraph(strategy=strategy, scope_registry=scope_registry)

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
