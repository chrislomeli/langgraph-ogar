"""
graph — LangGraph layer for the symbolic music agent.

This package contains the graph state, node functions, subgraphs,
and the graph builder that wires everything together.
"""

# Export the main components
from graph.m2.state import MusicGraphState, IntentType
from graph.m2.graph_builder import build_music_graph
from graph.m2.nodes import (
    intent_router, route_from_intent, INTENT_ROUTE_MAP,
    new_sketch, refine_plan, save_project, load_requests, answer_question
)

__all__ = [
    # State types
    "MusicGraphState",
    "IntentType",
    
    # Graph builder
    "build_music_graph",
    
    # Node functions
    "intent_router",
    "route_from_intent", 
    "INTENT_ROUTE_MAP",
    "new_sketch",
    "refine_plan", 
    "save_project",
    "load_requests",
    "answer_question"
]
