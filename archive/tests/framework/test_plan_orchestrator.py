"""Tests for planning.orchestrator — PlanOrchestrator lifecycle."""

from __future__ import annotations

import pytest

from framework.langgraph_ext.planning.approval import AlwaysApprove, AlwaysReview
from framework.langgraph_ext.planning.models import (
    PlanGraph,
    PlanPhase,
    RefinementRequest,
    SubPlan,
    SubPlanStatus,
)
from framework.langgraph_ext.planning.orchestrator import (
    EventKind,
    OrchestratorEvent,
    PlanOrchestrator,
    StepResult,
)
from framework.langgraph_ext.planning.registry import (
    NoOpExecutor,
    NoOpPlanner,
    ScopeRegistry,
    SubPlanExecutor,
    SubPlanPlanner,
)


# ── Test planners / executors ───────────────────────────────────────


class UpperPlanner(SubPlanPlanner):
    """Sets content to scope_id uppercased."""

    def plan(self, scope_id, plan, context=None):
        return scope_id.upper()


class ConcatExecutor(SubPlanExecutor):
    """Concatenates content from all upstream done sub-plans + own content."""

    def execute(self, sub_plan, plan, context=None):
        parts = []
        deps = plan.dependencies.get(sub_plan.scope_id, set())
        for dep_id in sorted(deps):
            dep = plan.sub_plans[dep_id]
            if dep.result is not None:
                parts.append(str(dep.result))
        parts.append(str(sub_plan.content))
        return " + ".join(parts)


class FailingExecutor(SubPlanExecutor):
    """Always raises."""

    def execute(self, sub_plan, plan, context=None):
        raise RuntimeError("boom")


# ── Helpers ─────────────────────────────────────────────────────────


def _sp(scope_id: str, scope_type: str = "generic", content=None) -> SubPlan:
    return SubPlan(scope_id=scope_id, scope_type=scope_type, content=content)


def _linear_plan() -> PlanGraph:
    """A → B → C, all with content pre-set."""
    return PlanGraph(
        title="linear",
        sub_plans={
            "a": _sp("a", content="alpha"),
            "b": _sp("b", content="beta"),
            "c": _sp("c", content="gamma"),
        },
        dependencies={"a": set(), "b": {"a"}, "c": {"b"}},
    )


def _parallel_plan() -> PlanGraph:
    """X and Y are independent roots, Z depends on both."""
    return PlanGraph(
        title="parallel",
        sub_plans={
            "x": _sp("x", content="ex"),
            "y": _sp("y", content="why"),
            "z": _sp("z", content="zee"),
        },
        dependencies={"x": set(), "y": set(), "z": {"x", "y"}},
    )


def _registry() -> ScopeRegistry:
    reg = ScopeRegistry()
    reg.register("generic", UpperPlanner(), ConcatExecutor())
    return reg


def _failing_registry() -> ScopeRegistry:
    reg = ScopeRegistry()
    reg.register("generic", UpperPlanner(), FailingExecutor())
    return reg


def _collect_events() -> tuple[list[OrchestratorEvent], "EventCallback"]:
    events: list[OrchestratorEvent] = []

    def callback(event: OrchestratorEvent):
        events.append(event)

    return events, callback


# ── Basic lifecycle ─────────────────────────────────────────────────


class TestOrchestratorBasic:
    def test_no_plan_raises(self):
        orch = PlanOrchestrator(registry=_registry())
        with pytest.raises(RuntimeError, match="No plan loaded"):
            orch.step()

    def test_load_plan(self):
        orch = PlanOrchestrator(registry=_registry())
        plan = _linear_plan()
        orch.load_plan(plan)
        assert orch.plan is plan
        assert orch.phase == PlanPhase.reviewing

    def test_propose_without_proposer_raises(self):
        orch = PlanOrchestrator(registry=_registry())
        with pytest.raises(RuntimeError, match="No PlanProposer"):
            orch.propose("do something")

    def test_phase_complete(self):
        orch = PlanOrchestrator(registry=_registry())
        plan = _linear_plan()
        orch.load_plan(plan)
        orch.run()
        assert orch.phase == PlanPhase.complete
        assert orch.is_complete


# ── Auto-approve run ────────────────────────────────────────────────


class TestAutoApproveRun:
    def test_linear_run_to_completion(self):
        orch = PlanOrchestrator(registry=_registry())
        orch.load_plan(_linear_plan())
        result = orch.run()
        assert result.complete
        assert orch.is_complete

        # Check results propagated
        plan = orch.plan
        assert plan.sub_plans["a"].status == SubPlanStatus.done
        assert plan.sub_plans["b"].status == SubPlanStatus.done
        assert plan.sub_plans["c"].status == SubPlanStatus.done
        assert plan.sub_plans["a"].result == "alpha"
        assert "alpha" in plan.sub_plans["b"].result
        assert "beta" in plan.sub_plans["b"].result

    def test_parallel_run(self):
        orch = PlanOrchestrator(registry=_registry())
        orch.load_plan(_parallel_plan())
        result = orch.run()
        assert result.complete
        plan = orch.plan
        assert plan.sub_plans["x"].status == SubPlanStatus.done
        assert plan.sub_plans["y"].status == SubPlanStatus.done
        assert plan.sub_plans["z"].status == SubPlanStatus.done

    def test_step_by_step_linear(self):
        orch = PlanOrchestrator(registry=_registry())
        orch.load_plan(_linear_plan())

        # Step 1: auto-approve all, execute "a" (only root is ready)
        r1 = orch.step()
        assert "a" in r1.executed
        assert "b" not in r1.executed  # b depends on a

        # Step 2: execute "b"
        r2 = orch.step()
        assert "b" in r2.executed

        # Step 3: execute "c"
        r3 = orch.step()
        assert "c" in r3.executed
        assert r3.complete

    def test_events_emitted(self):
        events, callback = _collect_events()
        orch = PlanOrchestrator(registry=_registry(), on_event=callback)
        orch.load_plan(_linear_plan())
        orch.run()

        kinds = [e.kind for e in events]
        assert EventKind.plan_proposed in kinds
        assert EventKind.sub_plan_auto_approved in kinds
        assert EventKind.sub_plan_executing in kinds
        assert EventKind.sub_plan_done in kinds
        assert EventKind.plan_complete in kinds


# ── Human-in-the-loop ───────────────────────────────────────────────


class TestHumanInTheLoop:
    def test_always_review_blocks(self):
        orch = PlanOrchestrator(
            registry=_registry(),
            approval_policy=AlwaysReview(),
        )
        orch.load_plan(_linear_plan())
        result = orch.step()
        # Nothing executed — everything needs approval
        assert result.executed == []
        assert len(result.awaiting_approval) > 0

    def test_approve_one_at_a_time(self):
        orch = PlanOrchestrator(
            registry=_registry(),
            approval_policy=AlwaysReview(),
        )
        orch.load_plan(_linear_plan())

        # Approve and step through
        orch.approve("a")
        r1 = orch.step()
        assert "a" in r1.executed

        orch.approve("b")
        r2 = orch.step()
        assert "b" in r2.executed

        orch.approve("c")
        r3 = orch.step()
        assert "c" in r3.executed
        assert r3.complete

    def test_approve_all(self):
        orch = PlanOrchestrator(
            registry=_registry(),
            approval_policy=AlwaysReview(),
        )
        orch.load_plan(_linear_plan())
        approved = orch.approve_all()
        assert set(approved) == {"a", "b", "c"}
        result = orch.run()
        assert result.complete

    def test_pending_approval_list(self):
        orch = PlanOrchestrator(
            registry=_registry(),
            approval_policy=AlwaysReview(),
        )
        orch.load_plan(_linear_plan())
        assert set(orch.pending_approval) == {"a", "b", "c"}
        orch.approve("a")
        assert "a" not in orch.pending_approval


# ── Failure handling ────────────────────────────────────────────────


class TestFailureHandling:
    def test_executor_failure_marks_failed(self):
        orch = PlanOrchestrator(registry=_failing_registry())
        plan = PlanGraph(
            sub_plans={"a": _sp("a", content="x")},
            dependencies={"a": set()},
        )
        orch.load_plan(plan)
        result = orch.step()
        assert "a" in result.failed
        assert plan.sub_plans["a"].status == SubPlanStatus.failed

    def test_failure_event_emitted(self):
        events, callback = _collect_events()
        orch = PlanOrchestrator(registry=_failing_registry(), on_event=callback)
        plan = PlanGraph(
            sub_plans={"a": _sp("a", content="x")},
            dependencies={"a": set()},
        )
        orch.load_plan(plan)
        orch.step()
        fail_events = [e for e in events if e.kind == EventKind.sub_plan_failed]
        assert len(fail_events) == 1
        assert fail_events[0].detail == "boom"


# ── Refinement ──────────────────────────────────────────────────────


class TestRefinement:
    def test_refine_invalidates_downstream(self):
        orch = PlanOrchestrator(registry=_registry())
        plan = _linear_plan()
        orch.load_plan(plan)
        orch.run()
        assert orch.is_complete

        # Refine "a" — should invalidate b and c
        req = RefinementRequest(prompt="change a", target_scopes=frozenset({"a"}))
        invalidated = orch.refine(req)
        assert invalidated == {"b", "c"}
        assert plan.sub_plans["a"].status == SubPlanStatus.draft
        assert plan.sub_plans["b"].status == SubPlanStatus.stale
        assert plan.sub_plans["c"].status == SubPlanStatus.stale
        assert not orch.is_complete

    def test_refine_then_run_to_completion(self):
        orch = PlanOrchestrator(registry=_registry())
        orch.load_plan(_linear_plan())
        orch.run()
        assert orch.is_complete

        req = RefinementRequest(prompt="change a", target_scopes=frozenset({"a"}))
        orch.refine(req)
        result = orch.run()
        assert result.complete
        assert orch.is_complete

    def test_refine_events(self):
        events, callback = _collect_events()
        orch = PlanOrchestrator(registry=_registry(), on_event=callback)
        orch.load_plan(_linear_plan())
        orch.run()
        events.clear()

        req = RefinementRequest(prompt="change a", target_scopes=frozenset({"a"}))
        orch.refine(req)
        kinds = [e.kind for e in events]
        assert EventKind.sub_plan_planned in kinds
        assert EventKind.sub_plan_stale in kinds
        assert EventKind.refinement_applied in kinds


# ── Max steps safety ────────────────────────────────────────────────


class TestMaxSteps:
    def test_max_steps_prevents_infinite_loop(self):
        orch = PlanOrchestrator(
            registry=_registry(),
            approval_policy=AlwaysReview(),
        )
        orch.load_plan(_linear_plan())
        result = orch.run(max_steps=2)
        assert not result.complete
        assert result.awaiting_approval
