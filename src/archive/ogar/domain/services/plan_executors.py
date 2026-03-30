"""
plan_executors — Domain-specific planner and executor implementations.

These are wired into the ScopeRegistry so the PlanOrchestrator can
dispatch planning and execution to the correct code per scope_type.

Scope types:
  - "goal_work"  — work to accomplish a goal
  - "validate"   — project consistency validation
  - "report"     — uncertainty/status reporting

All are deterministic stubs for now. Each can be swapped for LLM-backed
or tool-backed implementations later.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from ogar.planning.registry import SubPlanPlanner, SubPlanExecutor


# ── Fault injection ──────────────────────────────────────────────────

class FaultMode(str, Enum):
    """Configurable failure modes for testing."""
    none = "none"                    # always succeed
    transient = "transient"          # fail N times, then succeed
    permanent = "permanent"          # always fail
    timeout = "timeout"              # simulate timeout (raises TimeoutError)


# ── goal_work ────────────────────────────────────────────────────────

class GoalWorkPlanner(SubPlanPlanner):
    """Plan work items for a single goal. Stub: returns the content unchanged."""

    def plan(self, scope_id, plan, context=None):
        sp = plan.get(scope_id)
        return sp.content if sp else None


class GoalWorkExecutor(SubPlanExecutor):
    """
    Execute work for a goal.

    Supports fault injection for testing:
        GoalWorkExecutor()                          # always succeeds
        GoalWorkExecutor(FaultMode.transient, 2)    # fails twice, then succeeds
        GoalWorkExecutor(FaultMode.permanent)        # always fails
        GoalWorkExecutor(FaultMode.timeout)           # raises TimeoutError
    """

    def __init__(
        self,
        fault_mode: FaultMode = FaultMode.none,
        transient_failures: int = 0,
    ):
        self._fault_mode = fault_mode
        self._remaining_failures = transient_failures
        self._call_count = 0

    def execute(self, sub_plan, plan, context=None):
        self._call_count += 1
        goal_id = sub_plan.content.get("goal_id", "unknown") if sub_plan.content else "unknown"

        # Fault injection
        if self._fault_mode == FaultMode.permanent:
            raise RuntimeError(f"Permanent failure executing goal '{goal_id}'")

        if self._fault_mode == FaultMode.timeout:
            raise TimeoutError(f"Timeout executing goal '{goal_id}'")

        if self._fault_mode == FaultMode.transient and self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError(
                f"Transient failure executing goal '{goal_id}' "
                f"({self._remaining_failures} failures remaining)"
            )

        return {
            "goal_id": goal_id,
            "status": "completed",
            "attempts": self._call_count,
            "summary": f"Work for goal '{goal_id}' executed successfully.",
        }


# ── validate ─────────────────────────────────────────────────────────

class ValidatePlanner(SubPlanPlanner):
    """Plan validation. Stub: returns content unchanged."""

    def plan(self, scope_id, plan, context=None):
        sp = plan.get(scope_id)
        return sp.content if sp else None


class ValidateExecutor(SubPlanExecutor):
    """Run project validation. Stub: returns clean result."""

    def execute(self, sub_plan, plan, context=None):
        return {
            "validation_passed": True,
            "issues": [],
            "summary": "Project structure validated (stub).",
        }


# ── report ───────────────────────────────────────────────────────────

class ReportPlanner(SubPlanPlanner):
    """Plan reporting. Stub: returns content unchanged."""

    def plan(self, scope_id, plan, context=None):
        sp = plan.get(scope_id)
        return sp.content if sp else None


class ReportExecutor(SubPlanExecutor):
    """Generate reports. Stub: returns a canned summary."""

    def execute(self, sub_plan, plan, context=None):
        return {
            "report_type": "uncertainty_summary",
            "blocking_count": 0,
            "orphan_count": 0,
            "summary": "No blocking uncertainties found (stub).",
        }


# ── Registry builder ─────────────────────────────────────────────────

def build_default_registry():
    """Build a ScopeRegistry with all default (stub) implementations."""
    from ogar.planning.registry import ScopeRegistry

    registry = ScopeRegistry()
    registry.register("goal_work", GoalWorkPlanner(), GoalWorkExecutor())
    registry.register("validate", ValidatePlanner(), ValidateExecutor())
    registry.register("report", ReportPlanner(), ReportExecutor())
    return registry


def build_fault_registry(
    goal_fault: FaultMode = FaultMode.none,
    transient_failures: int = 0,
):
    """
    Build a ScopeRegistry with fault injection on goal_work executors.

    Use this for testing failure scenarios:
        build_fault_registry(FaultMode.transient, 2)  # fail twice then succeed
        build_fault_registry(FaultMode.permanent)       # always fail
    """
    from ogar.planning.registry import ScopeRegistry

    registry = ScopeRegistry()
    registry.register(
        "goal_work",
        GoalWorkPlanner(),
        GoalWorkExecutor(goal_fault, transient_failures),
    )
    registry.register("validate", ValidatePlanner(), ValidateExecutor())
    registry.register("report", ReportPlanner(), ReportExecutor())
    return registry
