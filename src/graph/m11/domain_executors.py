"""
Domain executors -- M11: SubPlanPlanner and SubPlanExecutor implementations.

KEY CONCEPT: The PlanOrchestrator is domain-agnostic. It drives a DAG of
SubPlans through their lifecycle (draft -> approved -> executing -> done).
Domain knowledge lives here -- in the planners and executors registered
with the ScopeRegistry.

For our music composition pipeline, the DAG has three stages:
  sketch_parse -> plan_composition -> compile_composition

Each stage has:
  - A SubPlanPlanner: produces the content for the SubPlan
  - A SubPlanExecutor: executes the SubPlan and produces a result

Since we're still deterministic (no LLM until M12), the planners produce
the content directly and the executors wrap the existing domain logic.
"""

from __future__ import annotations

from typing import Any

from framework.langgraph_ext.planning.registry import (
    SubPlanPlanner,
    SubPlanExecutor,
    ScopeRegistry,
)
from framework.langgraph_ext.planning.models import PlanGraph, SubPlan

from intent.sketch_models import Sketch
from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler
from intent.compiler_interface import CompileOptions


_planner = DeterministicPlanner()
_compiler = PatternCompiler()


# -- Sketch Parse --------------------------------------------------

class SketchParsePlanner(SubPlanPlanner):
    """Plans the sketch_parse step -- just stores the user message."""

    def plan(self, scope_id: str, plan: PlanGraph) -> Any:
        # Content is set externally (from user_message) before orchestration
        sp = plan.get(scope_id)
        return sp.content if sp else None


class SketchParseExecutor(SubPlanExecutor):
    """Executes sketch parsing: user message -> Sketch."""

    def execute(self, sub_plan: SubPlan, plan: PlanGraph) -> Any:
        user_message = sub_plan.content
        if not user_message:
            raise ValueError("No user message to parse")
        return Sketch(prompt=user_message)


# -- Plan Composition ----------------------------------------------

class PlanCompositionPlanner(SubPlanPlanner):
    """Plans the composition step -- needs the sketch from the previous step."""

    def plan(self, scope_id: str, plan: PlanGraph) -> Any:
        # The "plan" for this step is: use the sketch from sketch_parse
        sketch_sp = plan.get("sketch_parse")
        if sketch_sp and sketch_sp.result:
            return {"sketch": sketch_sp.result}
        return None


class PlanCompositionExecutor(SubPlanExecutor):
    """Executes planning: Sketch -> PlanBundle."""

    def execute(self, sub_plan: SubPlan, plan: PlanGraph) -> Any:
        sketch_sp = plan.get("sketch_parse")
        if not sketch_sp or not sketch_sp.result:
            raise ValueError("No sketch available from sketch_parse step")
        sketch = sketch_sp.result
        return _planner.plan(sketch)


# -- Compile Composition -------------------------------------------

class CompileCompositionPlanner(SubPlanPlanner):
    """Plans the compilation step -- needs the plan from the previous step."""

    def plan(self, scope_id: str, plan: PlanGraph) -> Any:
        plan_sp = plan.get("plan_composition")
        if plan_sp and plan_sp.result:
            return {"plan_bundle": plan_sp.result}
        return None


class CompileCompositionExecutor(SubPlanExecutor):
    """Executes compilation: PlanBundle -> CompileResult."""

    def execute(self, sub_plan: SubPlan, plan: PlanGraph) -> Any:
        plan_sp = plan.get("plan_composition")
        if not plan_sp or not plan_sp.result:
            raise ValueError("No PlanBundle available from plan_composition step")
        plan_bundle = plan_sp.result

        # Check for scoped recompilation hints
        content = sub_plan.content or {}
        regenerate_voices = content.get("regenerate_voices") if isinstance(content, dict) else None
        previous_result = content.get("previous_compile_result") if isinstance(content, dict) else None

        if regenerate_voices and previous_result:
            options = CompileOptions(regenerate_voices=regenerate_voices)
            return _compiler.compile(plan_bundle, options=options, previous=previous_result)
        return _compiler.compile(plan_bundle)


# -- Refinement Planner --------------------------------------------

class RefinementPlanner(SubPlanPlanner):
    """Re-plans a composition step after refinement request."""

    def plan(self, scope_id: str, plan: PlanGraph) -> Any:
        if scope_id == "plan_composition":
            # Re-plan: get the current plan result and apply refinement
            plan_sp = plan.get("plan_composition")
            if plan_sp and plan_sp.result:
                return {"plan_bundle": plan_sp.result, "needs_refine": True}
        return None


class RefinementExecutor(SubPlanExecutor):
    """Executes a refinement on the plan_composition step."""

    def execute(self, sub_plan: SubPlan, plan: PlanGraph) -> Any:
        content = sub_plan.content or {}
        if isinstance(content, dict) and content.get("needs_refine"):
            plan_bundle = content.get("plan_bundle")
            prompt = content.get("prompt", "")
            if plan_bundle and prompt:
                return _planner.refine(plan_bundle, prompt)
            return plan_bundle
        # Fallback: re-execute normally
        sketch_sp = plan.get("sketch_parse")
        if sketch_sp and sketch_sp.result:
            return _planner.plan(sketch_sp.result)
        raise ValueError("Cannot re-plan without sketch")


# -- Registry Builder ----------------------------------------------

def build_scope_registry() -> ScopeRegistry:
    """Build a ScopeRegistry with all domain planners and executors.

    Scope types:
      - sketch_parse: user message -> Sketch
      - plan_composition: Sketch -> PlanBundle
      - compile_composition: PlanBundle -> CompileResult
    """
    registry = ScopeRegistry()

    registry.register(
        "sketch_parse",
        SketchParsePlanner(),
        SketchParseExecutor(),
    )
    registry.register(
        "plan_composition",
        PlanCompositionPlanner(),
        PlanCompositionExecutor(),
    )
    registry.register(
        "compile_composition",
        CompileCompositionPlanner(),
        CompileCompositionExecutor(),
    )

    return registry


def build_creation_plan_graph(user_message: str) -> PlanGraph:
    """Build a PlanGraph DAG for the creation pipeline.

    DAG:
      sketch_parse -> plan_composition -> compile_composition

    Args:
        user_message: The user's free-text prompt.

    Returns:
        A PlanGraph ready for orchestration.
    """
    sketch_sp = SubPlan(
        scope_id="sketch_parse",
        scope_type="sketch_parse",
        content=user_message,
    )
    plan_sp = SubPlan(
        scope_id="plan_composition",
        scope_type="plan_composition",
    )
    compile_sp = SubPlan(
        scope_id="compile_composition",
        scope_type="compile_composition",
    )

    plan_graph = PlanGraph(
        title="Music Creation Pipeline",
        sub_plans={
            "sketch_parse": sketch_sp,
            "plan_composition": plan_sp,
            "compile_composition": compile_sp,
        },
        dependencies={
            "sketch_parse": set(),
            "plan_composition": {"sketch_parse"},
            "compile_composition": {"plan_composition"},
        },
    )

    return plan_graph
