"""
Graph builder — wires nodes and edges into a compiled LangGraph app.

YOUR JOB (M1):
  ✓ Built linear graph: START → process → presenter → END

YOUR JOB (M2):
  1. Import intent_router from graph.nodes.intent_router
  2. Import all stub nodes from graph.nodes.stub_nodes
  3. Define route_from_intent() function that maps intent_type to node names
  4. Update build_music_graph() to:
     - Add intent_router as the entry point
     - Add all stub nodes
     - Add conditional edges from intent_router via route_from_intent
     - Remove the old linear chain (process → presenter)

The graph should be:
  START → intent_router → [conditional] → stub nodes
"""
from langgraph.graph import StateGraph, START

from graph.m2.nodes import new_sketch, refine_plan, save_project, load_requests, answer_question, intent_router, route_from_intent, INTENT_ROUTE_MAP
from graph.m2.state import MusicGraphState


# ====================================================================
# STEP 7: Wire the graph
# ====================================================================

def build_music_graph():
    # Add type: ignore comments
    graph = StateGraph(MusicGraphState) # type: ignore

    graph.add_node("intent_router", intent_router)  # type: ignore
    graph.add_node("new_sketch", new_sketch)  # type: ignore
    graph.add_node("refine_plan", refine_plan)  # type: ignore
    graph.add_node("save_project", save_project)  # type: ignore
    graph.add_node("load_requests", load_requests)  # type: ignore
    graph.add_node("answer_question", answer_question)  # type: ignore

    graph.add_edge( START,  "intent_router" )# type: ignore
    graph.add_conditional_edges(
        "intent_router",
        route_from_intent,
        {
            node: node for node in INTENT_ROUTE_MAP.values()
        }
    )


    return  graph.compile()



