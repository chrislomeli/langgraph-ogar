"""
Refinement Subgraph — M9: Nodes call tools via LocalToolClient.

KEY CONCEPT: Same refinement pipeline as M8, but nodes call
tool_client.call() instead of domain logic directly.

Pipeline:
  START → scope_classifier → plan_refiner → compiler → presenter → END
"""

from langgraph.graph import StateGraph, START, END

from framework.langgraph_ext.tool_client.client import LocalToolClient
from framework.langgraph_ext.tool_client.registry import ToolRegistry

from ..state import RefinementState


def _scope_classifier(state: RefinementState) -> dict:
    """Determine what the user wants to change.

    Scope classification is routing logic, not a domain tool.
    Stays as direct code (like intent_router).
    """
    msg = state["user_message"].lower()
    previous_plan = state.get("previous_plan")

    if previous_plan is None:
        return {"changed_voice_ids": set(), "response": "Nothing to refine — no previous composition."}

    all_voice_ids = {v.voice_id for v in previous_plan.voice_plan.voices}

    if any(kw in msg for kw in ["add a", "remove the", "add bridge", "remove"]):
        return {"changed_voice_ids": all_voice_ids}

    if "busier" in msg or "sparser" in msg or "quieter" in msg:
        drum_ids = {
            v.voice_id for v in previous_plan.voice_plan.voices
            if v.role.value in ("drums", "percussion")
        }
        return {"changed_voice_ids": drum_ids if drum_ids else all_voice_ids}

    return {"changed_voice_ids": all_voice_ids}


def _make_plan_refiner(registry: ToolRegistry, tool_client: LocalToolClient):
    """Factory: plan_refiner node that calls refine_plan tool."""
    spec = registry.get("refine_plan")

    def plan_refiner(state: RefinementState) -> dict:
        previous_plan = state.get("previous_plan")
        if previous_plan is None:
            return {}

        validated = spec.input_model(plan=previous_plan, prompt=state["user_message"])
        output = spec.handler(validated)
        return {"plan": output.plan}
    return plan_refiner


def _make_compiler(registry: ToolRegistry, tool_client: LocalToolClient):
    """Factory: compiler node that calls compile_composition tool."""
    spec = registry.get("compile_composition")

    def compiler(state: RefinementState) -> dict:
        plan = state.get("plan")
        if plan is None:
            return {}

        previous_result = state.get("previous_compile_result")
        changed_ids = state.get("changed_voice_ids", set())

        args = {"plan": plan}
        if previous_result and changed_ids:
            all_voice_ids = {v.voice_id for v in plan.voice_plan.voices}
            unchanged_ids = all_voice_ids - changed_ids
            if unchanged_ids:
                args["regenerate_voices"] = changed_ids
                args["previous_compile_result"] = previous_result

        validated = spec.input_model(**args)
        output = spec.handler(validated)
        return {"compile_result": output.compile_result}
    return compiler


def _presenter(state: RefinementState) -> dict:
    """Summarize what the refinement changed."""
    plan = state.get("plan")
    if plan is None:
        return {}

    previous_plan = state.get("previous_plan")
    changed_ids = state.get("changed_voice_ids", set())
    result = state.get("compile_result")

    changes = []

    if previous_plan:
        old_sections = len(previous_plan.form_plan.sections)
        new_sections = len(plan.form_plan.sections)
        if new_sections != old_sections:
            changes.append(f"Sections: {old_sections} → {new_sections}")

        old_bars = previous_plan.form_plan.total_bars()
        new_bars = plan.form_plan.total_bars()
        if new_bars != old_bars:
            changes.append(f"Bars: {old_bars} → {new_bars}")

    if changed_ids:
        changed_names = []
        for v in plan.voice_plan.voices:
            if v.voice_id in changed_ids:
                changed_names.append(v.name)
        if changed_names:
            changes.append(f"Recompiled: {', '.join(changed_names)}")

    all_voice_ids = {v.voice_id for v in plan.voice_plan.voices}
    preserved_ids = all_voice_ids - (changed_ids or set())
    if preserved_ids:
        preserved_names = [
            v.name for v in plan.voice_plan.voices
            if v.voice_id in preserved_ids
        ]
        if preserved_names:
            changes.append(f"Preserved: {', '.join(preserved_names)}")

    track_count = len(result.composition.tracks)
    section_count = len(result.sections)

    change_summary = "; ".join(changes) if changes else "No changes detected"

    response = (
        f"Refined '{plan.title}' — {change_summary}.\n"
        f"Compiled: {track_count} tracks, {section_count} section versions."
    )

    return {"response": response}


def build_refinement_subgraph(tool_client: LocalToolClient):
    """Build the refinement subgraph with tool-backed nodes.

    Args:
        tool_client: LocalToolClient with registered tools.
    """
    registry = tool_client._registry
    builder = StateGraph(RefinementState)

    builder.add_node("scope_classifier", _scope_classifier)
    builder.add_node("plan_refiner", _make_plan_refiner(registry, tool_client))
    builder.add_node("compiler", _make_compiler(registry, tool_client))
    builder.add_node("presenter", _presenter)

    builder.add_edge(START, "scope_classifier")
    builder.add_edge("scope_classifier", "plan_refiner")
    builder.add_edge("plan_refiner", "compiler")
    builder.add_edge("compiler", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
