"""
Creation Subgraph -- M12: Strategy-backed PlanOrchestrator pipeline.

KEY CONCEPT: Same orchestrator-driven DAG as M11, but now the
PlanCompositionExecutor uses a PlannerStrategy (injected via
ScopeRegistry). Changing the strategy swaps the entire planning
backend without changing the graph topology.

The subgraph also records which strategy was used in state.
"""

from langgraph.graph import StateGraph, START, END

from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator, OrchestratorEvent
from framework.langgraph_ext.planning.approval import AlwaysApprove
from framework.langgraph_ext.planning.registry import ScopeRegistry

from ..state import CreationState
from ..domain_executors import build_scope_registry, build_creation_plan_graph
from ..planner_strategy import PlannerStrategy, DeterministicStrategy


def _make_orchestrate(scope_registry: ScopeRegistry, strategy: PlannerStrategy):
    """Factory: orchestrate node that drives the creation DAG."""

    def orchestrate(state: CreationState) -> dict:
        events = []

        def on_event(event: OrchestratorEvent):
            events.append({"kind": event.kind.value, "scope_id": event.scope_id, "detail": event.detail})

        plan_graph = build_creation_plan_graph(state["user_message"])

        orchestrator = PlanOrchestrator(
            registry=scope_registry,
            approval_policy=AlwaysApprove(),
            on_event=on_event,
        )
        orchestrator.load_plan(plan_graph)
        orchestrator.run()

        sketch = plan_graph.get("sketch_parse").result
        plan = plan_graph.get("plan_composition").result
        compile_result = plan_graph.get("compile_composition").result

        return {
            "sketch": sketch,
            "plan": plan,
            "compile_result": compile_result,
            "plan_graph": plan_graph,
            "orchestrator_events": events,
            "strategy_used": strategy.name,
        }

    return orchestrate


def _presenter(state: CreationState) -> dict:
    """Format a human-readable summary."""
    plan = state["plan"]
    result = state["compile_result"]
    strategy = state.get("strategy_used", "unknown")

    voice_names = ", ".join(v.name for v in plan.voice_plan.voices)
    track_count = len(result.composition.tracks)
    section_count = len(result.sections)

    response = (
        f"Created '{plan.title}' -- {plan.key} at {plan.tempo_bpm} BPM.\n"
        f"Voices: {voice_names}\n"
        f"Form: {plan.form_plan.total_bars()} bars across "
        f"{len(plan.form_plan.sections)} sections.\n"
        f"Compiled: {track_count} tracks, {section_count} section versions.\n"
        f"Strategy: {strategy}"
    )

    return {"response": response}


def build_creation_subgraph(
    strategy: PlannerStrategy | None = None,
    scope_registry: ScopeRegistry | None = None,
):
    """Build the creation subgraph with strategy-backed orchestrator.

    Args:
        strategy: PlannerStrategy to use. Defaults to DeterministicStrategy.
        scope_registry: ScopeRegistry. If None, built from strategy.
    """
    if strategy is None:
        strategy = DeterministicStrategy()
    if scope_registry is None:
        scope_registry = build_scope_registry(strategy=strategy)

    builder = StateGraph(CreationState)

    builder.add_node("orchestrate", _make_orchestrate(scope_registry, strategy))
    builder.add_node("presenter", _presenter)

    builder.add_edge(START, "orchestrate")
    builder.add_edge("orchestrate", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
