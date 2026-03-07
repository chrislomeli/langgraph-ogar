"""
Domain executors -- M12: Strategy-backed planners and executors.

KEY CONCEPT: Same DAG structure as M11, but the PlanCompositionExecutor
now uses a PlannerStrategy instead of hard-coding DeterministicPlanner.
This is the swap point: change the strategy and the whole pipeline
uses a different planning backend.
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
from intent.compiler import PatternCompiler
from intent.compiler_interface import CompileOptions

from .planner_strategy import PlannerStrategy, DeterministicStrategy


_compiler = PatternCompiler()


# -- Sketch Parse --------------------------------------------------

class SketchParsePlanner(SubPlanPlanner):
    def plan(self, scope_id: str, plan: PlanGraph) -> Any:
        sp = plan.get(scope_id)
        return sp.content if sp else None


class SketchParseExecutor(SubPlanExecutor):
    def execute(self, sub_plan: SubPlan, plan: PlanGraph) -> Any:
        user_message = sub_plan.content
        if not user_message:
            raise ValueError("No user message to parse")
        return Sketch(prompt=user_message)


# -- Plan Composition (strategy-backed) ----------------------------

class PlanCompositionPlanner(SubPlanPlanner):
    def plan(self, scope_id: str, plan: PlanGraph) -> Any:
        sketch_sp = plan.get("sketch_parse")
        if sketch_sp and sketch_sp.result:
            return {"sketch": sketch_sp.result}
        return None


class PlanCompositionExecutor(SubPlanExecutor):
    """Uses the injected PlannerStrategy instead of hard-coded engine."""

    def __init__(self, strategy: PlannerStrategy):
        self._strategy = strategy

    def execute(self, sub_plan: SubPlan, plan: PlanGraph) -> Any:
        sketch_sp = plan.get("sketch_parse")
        if not sketch_sp or not sketch_sp.result:
            raise ValueError("No sketch available from sketch_parse step")
        return self._strategy.plan(sketch_sp.result)


# -- Compile Composition -------------------------------------------

class CompileCompositionPlanner(SubPlanPlanner):
    def plan(self, scope_id: str, plan: PlanGraph) -> Any:
        plan_sp = plan.get("plan_composition")
        if plan_sp and plan_sp.result:
            return {"plan_bundle": plan_sp.result}
        return None


class CompileCompositionExecutor(SubPlanExecutor):
    def execute(self, sub_plan: SubPlan, plan: PlanGraph) -> Any:
        plan_sp = plan.get("plan_composition")
        if not plan_sp or not plan_sp.result:
            raise ValueError("No PlanBundle available from plan_composition step")
        plan_bundle = plan_sp.result

        content = sub_plan.content or {}
        regenerate_voices = content.get("regenerate_voices") if isinstance(content, dict) else None
        previous_result = content.get("previous_compile_result") if isinstance(content, dict) else None

        if regenerate_voices and previous_result:
            options = CompileOptions(regenerate_voices=regenerate_voices)
            return _compiler.compile(plan_bundle, options=options, previous=previous_result)
        return _compiler.compile(plan_bundle)


# -- Registry Builder ----------------------------------------------

def build_scope_registry(strategy: PlannerStrategy | None = None) -> ScopeRegistry:
    """Build a ScopeRegistry with strategy-backed executors.

    Args:
        strategy: PlannerStrategy for plan_composition.
                  Defaults to DeterministicStrategy.
    """
    if strategy is None:
        strategy = DeterministicStrategy()

    registry = ScopeRegistry()

    registry.register("sketch_parse", SketchParsePlanner(), SketchParseExecutor())
    registry.register("plan_composition", PlanCompositionPlanner(), PlanCompositionExecutor(strategy))
    registry.register("compile_composition", CompileCompositionPlanner(), CompileCompositionExecutor())

    return registry


def build_creation_plan_graph(user_message: str) -> PlanGraph:
    """Build a PlanGraph DAG for the creation pipeline."""
    sketch_sp = SubPlan(scope_id="sketch_parse", scope_type="sketch_parse", content=user_message)
    plan_sp = SubPlan(scope_id="plan_composition", scope_type="plan_composition")
    compile_sp = SubPlan(scope_id="compile_composition", scope_type="compile_composition")

    return PlanGraph(
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
