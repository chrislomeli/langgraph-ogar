"""
Refinement Subgraph -- M12: Strategy-backed refinement.

KEY CONCEPT: Same as M11 refinement but uses PlannerStrategy.refine()
instead of hard-coded DeterministicPlanner.refine(). The strategy is
injected at graph build time.
"""

from langgraph.graph import StateGraph, START, END

from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator, OrchestratorEvent
from framework.langgraph_ext.planning.approval import AlwaysApprove
from framework.langgraph_ext.planning.models import PlanGraph, SubPlan, SubPlanStatus
from framework.langgraph_ext.planning.registry import ScopeRegistry

from ..state import RefinementState
from ..domain_executors import build_scope_registry
from ..planner_strategy import PlannerStrategy, DeterministicStrategy

from intent.compiler import PatternCompiler
from intent.compiler_interface import CompileOptions

_compiler = PatternCompiler()


def _make_orchestrated_refine(scope_registry: ScopeRegistry, strategy: PlannerStrategy):
    """Factory: refinement node that uses strategy + orchestrator."""

    def orchestrated_refine(state: RefinementState) -> dict:
        previous_plan = state.get("previous_plan")
        previous_compile_result = state.get("previous_compile_result")

        if previous_plan is None:
            return {"response": "Nothing to refine -- no previous composition."}

        events = []

        def on_event(event: OrchestratorEvent):
            events.append({"kind": event.kind.value, "scope_id": event.scope_id, "detail": event.detail})

        # Apply refinement via strategy
        user_prompt = state["user_message"]
        refined_plan = strategy.refine(previous_plan, user_prompt)

        # Determine changed voices for scoped recompilation
        all_voice_ids = {v.voice_id for v in refined_plan.voice_plan.voices}
        msg = user_prompt.lower()
        if any(kw in msg for kw in ["add a", "remove the", "add bridge", "remove"]):
            changed_ids = all_voice_ids
        elif "busier" in msg or "sparser" in msg or "quieter" in msg:
            drum_ids = {
                v.voice_id for v in refined_plan.voice_plan.voices
                if v.role.value in ("drums", "percussion")
            }
            changed_ids = drum_ids if drum_ids else all_voice_ids
        else:
            changed_ids = all_voice_ids

        # Build a PlanGraph for re-compilation via orchestrator
        plan_graph = PlanGraph(
            title="Music Refinement Pipeline",
            sub_plans={
                "sketch_parse": SubPlan(
                    scope_id="sketch_parse", scope_type="sketch_parse",
                    content=user_prompt, status=SubPlanStatus.done, result=None,
                ),
                "plan_composition": SubPlan(
                    scope_id="plan_composition", scope_type="plan_composition",
                    content={"plan_bundle": refined_plan},
                    status=SubPlanStatus.done, result=refined_plan,
                ),
                "compile_composition": SubPlan(
                    scope_id="compile_composition", scope_type="compile_composition",
                    content={} if changed_ids == all_voice_ids else {
                        "regenerate_voices": changed_ids,
                        "previous_compile_result": previous_compile_result,
                    },
                    status=SubPlanStatus.approved,
                ),
            },
            dependencies={
                "sketch_parse": set(),
                "plan_composition": {"sketch_parse"},
                "compile_composition": {"plan_composition"},
            },
        )

        orchestrator = PlanOrchestrator(
            registry=scope_registry,
            approval_policy=AlwaysApprove(),
            on_event=on_event,
        )
        orchestrator.load_plan(plan_graph)
        orchestrator.run()

        compile_result = plan_graph.get("compile_composition").result

        return {
            "plan": refined_plan,
            "compile_result": compile_result,
            "changed_voice_ids": changed_ids,
            "plan_graph": plan_graph,
            "orchestrator_events": events,
            "strategy_used": strategy.name,
        }

    return orchestrated_refine


def _presenter(state: RefinementState) -> dict:
    """Summarize what the refinement changed."""
    plan = state.get("plan")
    if plan is None:
        return {}

    previous_plan = state.get("previous_plan")
    changed_ids = state.get("changed_voice_ids", set())
    result = state.get("compile_result")
    strategy = state.get("strategy_used", "unknown")

    changes = []

    if previous_plan:
        old_sections = len(previous_plan.form_plan.sections)
        new_sections = len(plan.form_plan.sections)
        if new_sections != old_sections:
            changes.append(f"Sections: {old_sections} -> {new_sections}")
        old_bars = previous_plan.form_plan.total_bars()
        new_bars = plan.form_plan.total_bars()
        if new_bars != old_bars:
            changes.append(f"Bars: {old_bars} -> {new_bars}")

    if changed_ids:
        changed_names = [v.name for v in plan.voice_plan.voices if v.voice_id in changed_ids]
        if changed_names:
            changes.append(f"Recompiled: {', '.join(changed_names)}")

    all_voice_ids = {v.voice_id for v in plan.voice_plan.voices}
    preserved_ids = all_voice_ids - (changed_ids or set())
    if preserved_ids:
        preserved_names = [v.name for v in plan.voice_plan.voices if v.voice_id in preserved_ids]
        if preserved_names:
            changes.append(f"Preserved: {', '.join(preserved_names)}")

    track_count = len(result.composition.tracks)
    section_count = len(result.sections)
    change_summary = "; ".join(changes) if changes else "No changes detected"

    response = (
        f"Refined '{plan.title}' -- {change_summary}.\n"
        f"Compiled: {track_count} tracks, {section_count} section versions.\n"
        f"Strategy: {strategy}"
    )

    return {"response": response}


def build_refinement_subgraph(
    strategy: PlannerStrategy | None = None,
    scope_registry: ScopeRegistry | None = None,
):
    """Build the refinement subgraph with strategy-backed orchestrator."""
    if strategy is None:
        strategy = DeterministicStrategy()
    if scope_registry is None:
        scope_registry = build_scope_registry(strategy=strategy)

    builder = StateGraph(RefinementState)

    builder.add_node("orchestrated_refine", _make_orchestrated_refine(scope_registry, strategy))
    builder.add_node("presenter", _presenter)

    builder.add_edge(START, "orchestrated_refine")
    builder.add_edge("orchestrated_refine", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
