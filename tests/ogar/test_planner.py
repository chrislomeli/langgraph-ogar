"""
Tests for the planner: PlanProposer, PlanOrchestrator wiring, and the
planner node in the outer graph.

Black-box: build domain objects, invoke planner logic, assert on output.
"""
import pytest

from ogar.domain.models.project import Project, Goal, Requirement
from ogar.domain.services.plan_proposer import ProjectPlanProposer
from ogar.domain.services.plan_executors import build_default_registry
from ogar.planning.orchestrator import PlanOrchestrator
from ogar.planning.models import SubPlanStatus


def _make_project(n_goals=2):
    """Helper: build a minimal Project with n goals and 1 requirement."""
    goals = {}
    for i in range(n_goals):
        gid = f"g_{i}"
        goals[gid] = Goal(gid=gid, statement=f"Goal {i}", success_metrics=[f"metric_{i}"])

    reqs = {}
    if n_goals > 0:
        reqs["r_0"] = Requirement(
            rid="r_0",
            type="functional",
            statement="Req 0",
            source_goal_ids=[f"g_0"],
        )

    return Project(pid="test", title="Test Project", goals=goals, requirements=reqs)


# ── PlanProposer ─────────────────────────────────────────────────────

class TestPlanProposer:
    """ProjectPlanProposer builds a valid PlanGraph from a Project."""

    def test_creates_subplan_per_goal(self):
        project = _make_project(n_goals=3)
        proposer = ProjectPlanProposer()
        plan = proposer.propose("test", context={"project": project})

        goal_sps = [sp for sp in plan.sub_plans.values() if sp.scope_type == "goal_work"]
        assert len(goal_sps) == 3

    def test_creates_validate_and_report(self):
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()
        plan = proposer.propose("test", context={"project": project})

        assert "validate" in plan.sub_plans
        assert "report" in plan.sub_plans

    def test_validate_depends_on_all_goals(self):
        project = _make_project(n_goals=2)
        proposer = ProjectPlanProposer()
        plan = proposer.propose("test", context={"project": project})

        validate_deps = plan.dependencies.get("validate", set())
        assert "work_g_0" in validate_deps
        assert "work_g_1" in validate_deps

    def test_report_depends_on_validate(self):
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()
        plan = proposer.propose("test", context={"project": project})

        assert "validate" in plan.dependencies.get("report", set())

    def test_goal_subplan_content_has_related_requirements(self):
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()
        plan = proposer.propose("test", context={"project": project})

        sp = plan.sub_plans["work_g_0"]
        assert "r_0" in sp.content["related_requirements"]


# ── Orchestrator wiring ──────────────────────────────────────────────

class TestOrchestratorWiring:
    """PlanOrchestrator runs the PlanGraph to completion with stubs."""

    def test_all_subplans_reach_done(self):
        project = _make_project(n_goals=2)
        proposer = ProjectPlanProposer()
        registry = build_default_registry()

        orch = PlanOrchestrator(registry=registry, proposer=proposer)
        plan = orch.propose("test", context={"project": project})
        result = orch.run()

        assert result.complete
        for sp in plan.sub_plans.values():
            assert sp.status == SubPlanStatus.done

    def test_events_emitted(self):
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()
        registry = build_default_registry()
        events = []

        orch = PlanOrchestrator(
            registry=registry,
            proposer=proposer,
            on_event=lambda e: events.append(e),
        )
        orch.propose("test", context={"project": project})
        orch.run()

        event_kinds = [e.kind.value for e in events]
        assert "plan_proposed" in event_kinds
        assert "plan_complete" in event_kinds
        assert "sub_plan_done" in event_kinds

    def test_dag_ordering_respected(self):
        """validate runs after goals, report runs after validate."""
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()
        registry = build_default_registry()
        executed_order = []

        def track(event):
            if event.kind.value == "sub_plan_done":
                executed_order.append(event.scope_id)

        orch = PlanOrchestrator(
            registry=registry,
            proposer=proposer,
            on_event=track,
        )
        orch.propose("test", context={"project": project})
        orch.run()

        # validate must come after goal work, report must come after validate
        assert executed_order.index("validate") > executed_order.index("work_g_0")
        assert executed_order.index("report") > executed_order.index("validate")


# ── Planner node edge cases ──────────────────────────────────────────

class TestPlannerEdgeCases:
    """Edge cases for the planner as used in the OGAR graph."""

    def test_no_goals_produces_empty_plan(self):
        """Call the planner node factory directly."""
        from ogar.runtime.graph.ogar_graph import _make_planner_node

        planner = _make_planner_node()
        state = {
            "pid": "test",
            "project": Project(pid="test", title="Empty"),
            "audit_log": [],
        }
        result = planner(state)
        assert result["plan_steps"] == []
        assert any("plan_skipped" in str(e) for e in result["audit_log"])

    def test_none_project_produces_empty_plan(self):
        from ogar.runtime.graph.ogar_graph import _make_planner_node

        planner = _make_planner_node()
        state = {
            "pid": "test",
            "project": None,
            "audit_log": [],
        }
        result = planner(state)
        assert result["plan_steps"] == []


# ── Fault injection ──────────────────────────────────────────────────

class TestFaultInjection:
    """
    Test the planner's behavior when executors fail.

    These tests exercise the PlanOrchestrator's error handling:
    - Transient failures: executor fails N times, then succeeds
    - Permanent failures: executor always fails, sub-plan marked failed
    """

    def test_transient_failure_marks_failed(self):
        """Transient faults: executor fails once, orchestrator marks sub-plan failed."""
        from ogar.domain.services.plan_executors import build_fault_registry, FaultMode

        registry = build_fault_registry(FaultMode.transient, 1)
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()

        orch = PlanOrchestrator(registry=registry, proposer=proposer)
        orch.propose("test", context={"project": project})
        orch.run()

        # The goal sub-plan should be failed (orchestrator caught the exception)
        plan = orch.plan
        assert plan.sub_plans["work_g_0"].status == SubPlanStatus.failed
        assert not orch.is_complete

    def test_permanent_failure_marks_failed(self):
        """Permanent faults should mark the sub-plan as failed."""
        from ogar.domain.services.plan_executors import build_fault_registry, FaultMode

        registry = build_fault_registry(FaultMode.permanent)
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()

        orch = PlanOrchestrator(registry=registry, proposer=proposer)
        orch.propose("test", context={"project": project})
        orch.run()

        plan = orch.plan
        assert plan.sub_plans["work_g_0"].status == SubPlanStatus.failed
        assert not orch.is_complete

    def test_permanent_failure_blocks_downstream(self):
        """If a goal fails, validate and report should NOT reach done."""
        from ogar.domain.services.plan_executors import build_fault_registry, FaultMode

        registry = build_fault_registry(FaultMode.permanent)
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()

        orch = PlanOrchestrator(registry=registry, proposer=proposer)
        orch.propose("test", context={"project": project})
        orch.run()

        plan = orch.plan
        assert plan.sub_plans["validate"].status != SubPlanStatus.done
        assert plan.sub_plans["report"].status != SubPlanStatus.done
        assert not orch.is_complete

    def test_fault_events_in_audit_log(self):
        """Failures should produce sub_plan_failed events."""
        from ogar.domain.services.plan_executors import build_fault_registry, FaultMode

        events = []
        registry = build_fault_registry(FaultMode.permanent)
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()

        orch = PlanOrchestrator(
            registry=registry,
            proposer=proposer,
            on_event=lambda e: events.append(e),
        )
        orch.propose("test", context={"project": project})
        orch.run()

        event_kinds = [e.kind.value for e in events]
        assert "sub_plan_failed" in event_kinds

    def test_timeout_treated_as_failure(self):
        """Timeout exceptions should also be caught and mark sub-plan failed."""
        from ogar.domain.services.plan_executors import build_fault_registry, FaultMode

        registry = build_fault_registry(FaultMode.timeout)
        project = _make_project(n_goals=1)
        proposer = ProjectPlanProposer()

        orch = PlanOrchestrator(registry=registry, proposer=proposer)
        orch.propose("test", context={"project": project})
        orch.run()

        assert orch.plan.sub_plans["work_g_0"].status == SubPlanStatus.failed
        assert not orch.is_complete
