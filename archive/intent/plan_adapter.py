"""
Plan adapter: bridges the music intent layer with the generic plan framework.

Maps the existing PlanBundle sub-plans (VoicePlan, FormPlan, HarmonyPlan,
GroovePlan, RenderPlan) onto the framework's SubPlan/PlanGraph/ScopeRegistry
model.

Music DAG:
    [voices] ──► [form] ──► [harmony] ──► [compilation]
                       └──► [groove] ──────┘

Usage:
    from intent.plan_adapter import music_registry, bundle_to_plan_graph

    # Convert an existing PlanBundle into a PlanGraph
    graph = bundle_to_plan_graph(bundle)

    # Run through the orchestrator
    orch = PlanOrchestrator(registry=music_registry())
    orch.load_plan(graph)
    orch.run()

    # Extract results back to a PlanBundle
    new_bundle = plan_graph_to_bundle(graph, original_bundle)
"""

from __future__ import annotations

from typing import Any, Optional

from framework.langgraph_ext.planning.models import PlanGraph, SubPlan
from framework.langgraph_ext.planning.registry import (
    ScopeRegistry,
    SubPlanExecutor,
    SubPlanPlanner,
)

from intent.plan_models import (
    FormPlan,
    GroovePlan,
    HarmonyPlan,
    PlanBundle,
    RenderPlan,
    VoicePlan,
)
from intent.compiler_interface import CompileOptions, CompileResult


# ── Scope type constants ────────────────────────────────────────────

SCOPE_VOICES = "voices"
SCOPE_FORM = "form"
SCOPE_HARMONY = "harmony"
SCOPE_GROOVE = "groove"
SCOPE_COMPILATION = "compilation"

ALL_SCOPES = [SCOPE_VOICES, SCOPE_FORM, SCOPE_HARMONY, SCOPE_GROOVE, SCOPE_COMPILATION]

# Music DAG dependencies
MUSIC_DEPENDENCIES: dict[str, set[str]] = {
    SCOPE_VOICES: set(),
    SCOPE_FORM: {SCOPE_VOICES},
    SCOPE_HARMONY: {SCOPE_FORM},
    SCOPE_GROOVE: {SCOPE_FORM},
    SCOPE_COMPILATION: {SCOPE_HARMONY, SCOPE_GROOVE},
}


# ── Conversion: PlanBundle → PlanGraph ──────────────────────────────


def bundle_to_plan_graph(bundle: PlanBundle) -> PlanGraph:
    """
    Convert an existing PlanBundle into a PlanGraph.

    Each sub-plan in the bundle becomes a SubPlan node in the DAG,
    with the Pydantic model as its content.
    """
    return PlanGraph(
        title=bundle.title,
        sub_plans={
            SCOPE_VOICES: SubPlan(
                scope_id=SCOPE_VOICES,
                scope_type=SCOPE_VOICES,
                content=bundle.voice_plan.model_dump(),
            ),
            SCOPE_FORM: SubPlan(
                scope_id=SCOPE_FORM,
                scope_type=SCOPE_FORM,
                content=bundle.form_plan.model_dump(),
            ),
            SCOPE_HARMONY: SubPlan(
                scope_id=SCOPE_HARMONY,
                scope_type=SCOPE_HARMONY,
                content=bundle.harmony_plan.model_dump(),
            ),
            SCOPE_GROOVE: SubPlan(
                scope_id=SCOPE_GROOVE,
                scope_type=SCOPE_GROOVE,
                content=bundle.groove_plan.model_dump(),
            ),
            SCOPE_COMPILATION: SubPlan(
                scope_id=SCOPE_COMPILATION,
                scope_type=SCOPE_COMPILATION,
                content=None,
            ),
        },
        dependencies=MUSIC_DEPENDENCIES,
    )


# ── Conversion: PlanGraph → PlanBundle ──────────────────────────────


def plan_graph_to_bundle(graph: PlanGraph, original: PlanBundle) -> PlanBundle:
    """
    Extract sub-plan content from a PlanGraph back into a PlanBundle.

    Uses the original bundle as a template for global fields (key, tempo, etc.)
    and overwrites sub-plans with the graph's content.
    """
    def _extract(scope_id: str, model_cls):
        sp = graph.sub_plans[scope_id]
        if sp.content is not None and isinstance(sp.content, dict):
            return model_cls(**sp.content)
        # Fall back to original if content wasn't re-planned
        return getattr(original, f"{scope_id}_plan", None)

    return PlanBundle(
        bundle_id=original.bundle_id,
        sketch_id=original.sketch_id,
        title=original.title,
        key=original.key,
        tempo_bpm=original.tempo_bpm,
        time_signature=original.time_signature,
        voice_plan=_extract(SCOPE_VOICES, VoicePlan) or original.voice_plan,
        form_plan=_extract(SCOPE_FORM, FormPlan) or original.form_plan,
        harmony_plan=_extract(SCOPE_HARMONY, HarmonyPlan) or original.harmony_plan,
        groove_plan=_extract(SCOPE_GROOVE, GroovePlan) or original.groove_plan,
        render_plan=original.render_plan,
    )


# ── Planners ────────────────────────────────────────────────────────
# These are thin wrappers — the real planning logic stays in
# DeterministicPlanner (or a future LLM engine). These just
# extract the relevant sub-plan content from the graph context.


class VoicePlanner(SubPlanPlanner):
    """Passes through existing voice plan content (no re-planning)."""

    def plan(self, scope_id, plan, context=None):
        sp = plan.sub_plans.get(scope_id)
        return sp.content if sp else None


class FormPlanner(SubPlanPlanner):
    """Passes through existing form plan content."""

    def plan(self, scope_id, plan, context=None):
        sp = plan.sub_plans.get(scope_id)
        return sp.content if sp else None


class HarmonyPlanner(SubPlanPlanner):
    """Passes through existing harmony plan content."""

    def plan(self, scope_id, plan, context=None):
        sp = plan.sub_plans.get(scope_id)
        return sp.content if sp else None


class GroovePlanner(SubPlanPlanner):
    """Passes through existing groove plan content."""

    def plan(self, scope_id, plan, context=None):
        sp = plan.sub_plans.get(scope_id)
        return sp.content if sp else None


class CompilationPlanner(SubPlanPlanner):
    """Compilation has no content to plan — it's an execution-only step."""

    def plan(self, scope_id, plan, context=None):
        return {"ready": True}


# ── Executors ───────────────────────────────────────────────────────
# Validation executors: each checks that its sub-plan content is a
# valid Pydantic model. The compilation executor actually compiles.


class VoiceExecutor(SubPlanExecutor):
    """Validates voice plan content."""

    def execute(self, sub_plan, plan, context=None):
        if sub_plan.content and isinstance(sub_plan.content, dict):
            vp = VoicePlan(**sub_plan.content)
            return f"VoicePlan OK: {len(vp.voices)} voices"
        return "VoicePlan: no content"


class FormExecutor(SubPlanExecutor):
    """Validates form plan content."""

    def execute(self, sub_plan, plan, context=None):
        if sub_plan.content and isinstance(sub_plan.content, dict):
            fp = FormPlan(**sub_plan.content)
            return f"FormPlan OK: {len(fp.sections)} sections, {fp.total_bars()} bars"
        return "FormPlan: no content"


class HarmonyExecutor(SubPlanExecutor):
    """Validates harmony plan content."""

    def execute(self, sub_plan, plan, context=None):
        if sub_plan.content and isinstance(sub_plan.content, dict):
            hp = HarmonyPlan(**sub_plan.content)
            return f"HarmonyPlan OK: {len(hp.sections)} sections"
        return "HarmonyPlan: no content"


class GrooveExecutor(SubPlanExecutor):
    """Validates groove plan content."""

    def execute(self, sub_plan, plan, context=None):
        if sub_plan.content and isinstance(sub_plan.content, dict):
            gp = GroovePlan(**sub_plan.content)
            return f"GroovePlan OK: {len(gp.sections)} sections"
        return "GroovePlan: no content"


class CompilationExecutor(SubPlanExecutor):
    """
    Compiles the plan into Composition IR.

    Requires a PlanCompiler and the original PlanBundle in context.
    """

    def __init__(self, compiler=None):
        self._compiler = compiler

    def execute(self, sub_plan, plan, context=None):
        if self._compiler is None:
            return "Compilation: no compiler registered (dry run)"

        # Reconstruct PlanBundle from graph content + context
        original_bundle = context.get("original_bundle") if context else None
        if original_bundle is None:
            return "Compilation: no original_bundle in context"

        bundle = plan_graph_to_bundle(plan, original_bundle)
        result = self._compiler.compile(bundle)
        return f"Compiled: {len(result.sections)} sections, {len(result.warnings)} warnings"


# ── Registry factory ────────────────────────────────────────────────


def music_registry(compiler=None) -> ScopeRegistry:
    """
    Create a ScopeRegistry pre-loaded with music domain planners and executors.

    Args:
        compiler: Optional PlanCompiler instance for the compilation step.
            If None, compilation runs in dry-run mode.
    """
    reg = ScopeRegistry()
    reg.register(SCOPE_VOICES, VoicePlanner(), VoiceExecutor())
    reg.register(SCOPE_FORM, FormPlanner(), FormExecutor())
    reg.register(SCOPE_HARMONY, HarmonyPlanner(), HarmonyExecutor())
    reg.register(SCOPE_GROOVE, GroovePlanner(), GrooveExecutor())
    reg.register(SCOPE_COMPILATION, CompilationPlanner(), CompilationExecutor(compiler))
    return reg
