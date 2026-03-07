"""Tests for planning.registry — ScopeRegistry and extension points."""

from __future__ import annotations

import pytest

from framework.langgraph_ext.planning.models import PlanGraph, SubPlan
from framework.langgraph_ext.planning.registry import (
    NoOpExecutor,
    NoOpPlanner,
    ScopeRegistry,
    SubPlanExecutor,
    SubPlanPlanner,
)


# ── Concrete test implementations ───────────────────────────────────


class EchoPlanner(SubPlanPlanner):
    """Returns scope_id as content for testing."""

    def plan(self, scope_id, plan, context=None):
        return {"planned": scope_id}


class DoubleExecutor(SubPlanExecutor):
    """Returns content doubled for testing."""

    def execute(self, sub_plan, plan, context=None):
        if sub_plan.content and isinstance(sub_plan.content, dict):
            return {"result": sub_plan.content.get("planned", "") * 2}
        return None


# ── ScopeRegistry ───────────────────────────────────────────────────


class TestScopeRegistry:
    def test_register_and_retrieve(self):
        reg = ScopeRegistry()
        reg.register("harmony", EchoPlanner(), DoubleExecutor())
        assert reg.has("harmony")
        assert isinstance(reg.get_planner("harmony"), EchoPlanner)
        assert isinstance(reg.get_executor("harmony"), DoubleExecutor)

    def test_registered_types(self):
        reg = ScopeRegistry()
        reg.register("b_type", NoOpPlanner(), NoOpExecutor())
        reg.register("a_type", NoOpPlanner(), NoOpExecutor())
        assert reg.registered_types() == ["a_type", "b_type"]

    def test_duplicate_register_raises(self):
        reg = ScopeRegistry()
        reg.register("harmony", EchoPlanner(), DoubleExecutor())
        with pytest.raises(ValueError, match="already registered"):
            reg.register("harmony", EchoPlanner(), DoubleExecutor())

    def test_get_planner_unknown_raises(self):
        reg = ScopeRegistry()
        with pytest.raises(KeyError, match="No registration"):
            reg.get_planner("nonexistent")

    def test_get_executor_unknown_raises(self):
        reg = ScopeRegistry()
        with pytest.raises(KeyError, match="No registration"):
            reg.get_executor("nonexistent")

    def test_has_returns_false_for_unknown(self):
        reg = ScopeRegistry()
        assert not reg.has("nonexistent")


# ── NoOp implementations ───────────────────────────────────────────


class TestNoOps:
    def test_noop_planner_returns_none(self):
        planner = NoOpPlanner()
        g = PlanGraph(title="test")
        assert planner.plan("x", g) is None

    def test_noop_executor_returns_none(self):
        executor = NoOpExecutor()
        sp = SubPlan(scope_id="x", scope_type="generic")
        g = PlanGraph(title="test")
        assert executor.execute(sp, g) is None


# ── Integration: engine + executor round-trip ──────────────────────


class TestPlannerExecutorRoundTrip:
    def test_echo_planner_then_double_executor(self):
        planner = EchoPlanner()
        executor = DoubleExecutor()

        g = PlanGraph(
            sub_plans={"h": SubPlan(scope_id="h", scope_type="harmony")},
            dependencies={"h": set()},
        )

        content = planner.plan("h", g)
        assert content == {"planned": "h"}

        sp = g.sub_plans["h"]
        sp.set_content(content, planned_by="echo")
        result = executor.execute(sp, g)
        assert result == {"result": "hh"}
