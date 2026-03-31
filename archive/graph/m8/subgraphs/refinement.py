"""
Refinement Subgraph — M8: Scoped recompilation with merge.

Pipeline:
  START → scope_classifier → plan_refiner → compiler → merge_assembler → presenter → END

KEY CONCEPTS:
  - scope_classifier: determines WHAT changed (which voices need recompilation)
  - plan_refiner: applies the change to the plan via DeterministicPlanner.refine()
  - compiler: recompiles the FULL plan (PatternCompiler handles scoped regen internally)
  - merge_assembler: merges new compilation with previous, preserving unchanged voices
  - presenter: summarizes what changed

The refinement subgraph receives:
  - user_message: what the user wants to change ("make the chorus busier")
  - previous_plan: the plan before refinement
  - previous_compile_result: the compilation before refinement

It produces:
  - plan: the refined plan
  - compile_result: the new compilation (with unchanged voices preserved)
  - changed_voice_ids: which voices were recompiled
  - response: human-readable summary of what changed
"""

from langgraph.graph import StateGraph, START, END

from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler
from intent.compiler_interface import CompileOptions

from ..state import RefinementState


_planner = DeterministicPlanner()
_compiler = PatternCompiler()


def scope_classifier(state: RefinementState) -> dict:
    """Determine what the user wants to change.

    Compares the refinement prompt against the current plan to
    identify which voices will be affected. In production, an LLM
    would do this. Here we use simple keyword matching.

    KEY CONCEPT: This is the "what changed?" step. It determines
    the scope of recompilation — only affected voices get recompiled.
    """
    msg = state["user_message"].lower()
    previous_plan = state.get("previous_plan")

    if previous_plan is None:
        return {"changed_voice_ids": set(), "response": "Nothing to refine — no previous composition."}

    # Determine which voices are affected by the refinement
    all_voice_ids = {v.voice_id for v in previous_plan.voice_plan.voices}

    # "add a bridge" or "remove the intro" → structural change → all voices
    if any(kw in msg for kw in ["add a", "remove the", "add bridge", "remove"]):
        return {"changed_voice_ids": all_voice_ids}

    # "make the chorus busier" → groove change → drums and percussion
    if "busier" in msg or "sparser" in msg or "quieter" in msg:
        drum_ids = {
            v.voice_id for v in previous_plan.voice_plan.voices
            if v.role.value in ("drums", "percussion")
        }
        return {"changed_voice_ids": drum_ids if drum_ids else all_voice_ids}

    # Default: recompile everything
    return {"changed_voice_ids": all_voice_ids}


def plan_refiner(state: RefinementState) -> dict:
    """Apply the refinement to the plan.

    Uses DeterministicPlanner.refine() which handles:
      - "add a bridge" → inserts bridge section
      - "remove the intro" → removes section
      - "make the chorus busier" → adjusts density

    The refined plan replaces the current plan in state.
    """
    previous_plan = state.get("previous_plan")
    if previous_plan is None:
        return {}  # Nothing to refine — scope_classifier already set the response

    prompt = state["user_message"]
    refined_plan = _planner.refine(previous_plan, prompt)

    return {"plan": refined_plan}


def compiler(state: RefinementState) -> dict:
    """Recompile with the refined plan.

    Uses PatternCompiler with scoped regeneration:
    only voices in changed_voice_ids are recompiled.
    Unchanged voices are preserved from the previous result.
    """
    plan = state.get("plan")
    if plan is None:
        return {}  # Nothing to compile

    previous_result = state.get("previous_compile_result")
    changed_ids = state.get("changed_voice_ids", set())

    if previous_result and changed_ids:
        # Scoped recompilation — only recompile changed voices
        all_voice_ids = {v.voice_id for v in plan.voice_plan.voices}
        unchanged_ids = all_voice_ids - changed_ids

        if unchanged_ids:
            # Tell the compiler to only regenerate changed voices
            options = CompileOptions(regenerate_voices=changed_ids)
            result = _compiler.compile(plan, options=options, previous=previous_result)
        else:
            # Everything changed — full recompile
            result = _compiler.compile(plan)
    else:
        # No previous result — full compile
        result = _compiler.compile(plan)

    return {"compile_result": result}


def presenter(state: RefinementState) -> dict:
    """Summarize what the refinement changed."""
    plan = state.get("plan")
    if plan is None:
        return {}  # scope_classifier already set the response

    previous_plan = state.get("previous_plan")
    changed_ids = state.get("changed_voice_ids", set())
    result = state.get("compile_result")

    # Describe what changed
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
        # Find voice names for the changed IDs
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


def build_refinement_subgraph():
    """Build the refinement subgraph.

    Graph:
      START → scope_classifier → plan_refiner → compiler → presenter → END
    """
    builder = StateGraph(RefinementState)

    builder.add_node("scope_classifier", scope_classifier)
    builder.add_node("plan_refiner", plan_refiner)
    builder.add_node("compiler", compiler)
    builder.add_node("presenter", presenter)

    builder.add_edge(START, "scope_classifier")
    builder.add_edge("scope_classifier", "plan_refiner")
    builder.add_edge("plan_refiner", "compiler")
    builder.add_edge("compiler", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
