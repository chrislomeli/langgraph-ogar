"""
Creation Subgraph -- M11: PlanOrchestrator-driven pipeline.

KEY CONCEPT: Instead of a linear chain of nodes (sketch_parser -> engine ->
compiler -> presenter), the creation pipeline is now expressed as a PlanGraph
DAG and driven by the PlanOrchestrator.

The orchestrator:
  1. Builds a PlanGraph DAG: sketch_parse -> plan_composition -> compile_composition
  2. Auto-approves all steps (AlwaysApprove policy)
  3. Executes each step via domain executors registered in the ScopeRegistry
  4. Collects events and results

The LangGraph subgraph has just two nodes:
  - orchestrate: builds DAG and runs the orchestrator
  - presenter: formats the result (same as before)

This shows how the PlanOrchestrator can manage complex multi-step pipelines
while keeping nodes simple.
"""

from langgraph.graph import StateGraph, START, END

from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator, OrchestratorEvent
from framework.langgraph_ext.planning.approval import AlwaysApprove
from framework.langgraph_ext.planning.registry import ScopeRegistry

from ..state import CreationState
from ..domain_executors import build_scope_registry, build_creation_plan_graph


def _make_orchestrate(scope_registry: ScopeRegistry):
    """Factory: orchestrate node that drives the creation DAG."""

    def orchestrate(state: CreationState) -> dict:
        # Collect events for observability
        events = []

        def on_event(event: OrchestratorEvent):
            events.append({"kind": event.kind.value, "scope_id": event.scope_id, "detail": event.detail})

        # Build the DAG
        plan_graph = build_creation_plan_graph(state["user_message"])

        # Create and run the orchestrator
        orchestrator = PlanOrchestrator(
            registry=scope_registry,
            approval_policy=AlwaysApprove(),
            on_event=on_event,
        )
        orchestrator.load_plan(plan_graph)
        orchestrator.run()

        # Extract results from completed sub-plans
        sketch = plan_graph.get("sketch_parse").result
        plan = plan_graph.get("plan_composition").result
        compile_result = plan_graph.get("compile_composition").result

        return {
            "sketch": sketch,
            "plan": plan,
            "compile_result": compile_result,
            "plan_graph": plan_graph,
            "orchestrator_events": events,
        }

    return orchestrate


def _presenter(state: CreationState) -> dict:
    """Format a human-readable summary."""
    plan = state["plan"]
    result = state["compile_result"]

    voice_names = ", ".join(v.name for v in plan.voice_plan.voices)
    track_count = len(result.composition.tracks)
    section_count = len(result.sections)

    response = (
        f"Created '{plan.title}' -- {plan.key} at {plan.tempo_bpm} BPM.\n"
        f"Voices: {voice_names}\n"
        f"Form: {plan.form_plan.total_bars()} bars across "
        f"{len(plan.form_plan.sections)} sections.\n"
        f"Compiled: {track_count} tracks, {section_count} section versions."
    )

    return {"response": response}


def build_creation_subgraph(scope_registry: ScopeRegistry | None = None):
    """Build the creation subgraph with PlanOrchestrator.

    Args:
        scope_registry: ScopeRegistry with domain executors.
                       If None, one is created automatically.
    """
    if scope_registry is None:
        scope_registry = build_scope_registry()

    builder = StateGraph(CreationState)

    builder.add_node("orchestrate", _make_orchestrate(scope_registry))
    builder.add_node("presenter", _presenter)

    builder.add_edge(START, "orchestrate")
    builder.add_edge("orchestrate", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
