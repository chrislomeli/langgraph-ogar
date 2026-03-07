"""
PlanOrchestrator — Drives a PlanGraph through its lifecycle.

The orchestrator is the "project manager": it coordinates planning,
approval, execution, and refinement without knowing anything about
the domain.  Domain knowledge lives in registered planners and
executors (see registry.py).

Design:
  - Pure Python class, no LangGraph dependency.
  - Synchronous step-based API: call ``step()`` repeatedly or
    ``run()`` to drive to completion.
  - Pluggable approval policy controls human-in-the-loop.
  - Emits events (callbacks) so callers can observe/log/intercept.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from ogar.planning.approval import AlwaysApprove, ApprovalPolicy
from ogar.planning.dag import (
    invalidate_downstream,
    ready_to_execute,
    leaves,
)
from ogar.planning.models import (
    PlanGraph,
    PlanPhase,
    RefinementRequest,
    SubPlanStatus,
)
from ogar.planning.registry import ScopeRegistry

logger = logging.getLogger(__name__)


# ── Events ──────────────────────────────────────────────────────────


class EventKind(str, Enum):
    """Types of orchestrator events."""

    plan_proposed = "plan_proposed"
    sub_plan_planned = "sub_plan_planned"
    sub_plan_approved = "sub_plan_approved"
    sub_plan_auto_approved = "sub_plan_auto_approved"
    sub_plan_executing = "sub_plan_executing"
    sub_plan_done = "sub_plan_done"
    sub_plan_failed = "sub_plan_failed"
    sub_plan_stale = "sub_plan_stale"
    awaiting_approval = "awaiting_approval"
    refinement_applied = "refinement_applied"
    plan_complete = "plan_complete"
    step_no_progress = "step_no_progress"


@dataclass(frozen=True)
class OrchestratorEvent:
    """An event emitted by the orchestrator during execution."""

    kind: EventKind
    scope_id: Optional[str] = None
    detail: Optional[str] = None


EventCallback = Callable[[OrchestratorEvent], None]


# ── Step result ─────────────────────────────────────────────────────


@dataclass
class StepResult:
    """Returned by ``step()`` to describe what happened."""

    executed: list[str] = field(default_factory=list)
    auto_approved: list[str] = field(default_factory=list)
    awaiting_approval: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    complete: bool = False
    no_progress: bool = False


# ── Orchestrator ────────────────────────────────────────────────────


class PlanOrchestrator:
    """
    Drives a PlanGraph through its lifecycle.

    Usage (auto-approve mode):
        orchestrator = PlanOrchestrator(registry=registry)
        orchestrator.load_plan(plan)
        orchestrator.run()

    Usage (human-in-the-loop):
        orchestrator = PlanOrchestrator(registry=registry, approval_policy=AlwaysReview())
        orchestrator.load_plan(plan)
        while not orchestrator.is_complete:
            result = orchestrator.step()
            if result.awaiting_approval:
                for sid in result.awaiting_approval:
                    orchestrator.approve(sid)
    """

    def __init__(
        self,
        registry: ScopeRegistry,
        proposer: Optional[Any] = None,
        approval_policy: Optional[ApprovalPolicy] = None,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self._registry = registry
        self._proposer = proposer
        self._policy = approval_policy or AlwaysApprove()
        self._on_event = on_event
        self._plan: Optional[PlanGraph] = None

    # ── Properties ──────────────────────────────────────────────────

    @property
    def plan(self) -> Optional[PlanGraph]:
        return self._plan

    @property
    def phase(self) -> PlanPhase:
        if self._plan is None:
            return PlanPhase.proposing
        if self._plan.all_leaves_done():
            return PlanPhase.complete
        if any(sp.status == SubPlanStatus.executing for sp in self._plan.sub_plans.values()):
            return PlanPhase.executing
        if any(sp.status == SubPlanStatus.draft for sp in self._plan.sub_plans.values()):
            return PlanPhase.reviewing
        return PlanPhase.executing

    @property
    def is_complete(self) -> bool:
        return self._plan is not None and self._plan.all_leaves_done()

    @property
    def pending_approval(self) -> list[str]:
        if self._plan is None:
            return []
        return sorted(
            sid for sid, sp in self._plan.sub_plans.items()
            if sp.status == SubPlanStatus.draft
            and self._policy.needs_approval(sp, self._plan)
        )

    # ── Plan setup ──────────────────────────────────────────────────

    def load_plan(self, plan: PlanGraph) -> None:
        """Load an externally-constructed plan."""
        self._plan = plan
        self._emit(OrchestratorEvent(kind=EventKind.plan_proposed))

    def propose(self, intent: str, context: Optional[dict[str, Any]] = None) -> PlanGraph:
        """Use the registered proposer to create a plan from intent."""
        if self._proposer is None:
            raise RuntimeError("No PlanProposer registered. Use load_plan() instead.")
        self._plan = self._proposer.propose(intent, context)
        self._emit(OrchestratorEvent(kind=EventKind.plan_proposed))
        return self._plan

    # ── Approval ────────────────────────────────────────────────────

    def approve(self, scope_id: str) -> None:
        """Manually approve a draft sub-plan."""
        self._require_plan()
        sp = self._get_sub_plan(scope_id)
        sp.approve()
        self._emit(OrchestratorEvent(kind=EventKind.sub_plan_approved, scope_id=scope_id))

    def approve_all(self) -> list[str]:
        """Approve all draft sub-plans. Returns approved scope_ids."""
        self._require_plan()
        approved = []
        for sid, sp in self._plan.sub_plans.items():
            if sp.status == SubPlanStatus.draft:
                sp.approve()
                approved.append(sid)
                self._emit(OrchestratorEvent(kind=EventKind.sub_plan_approved, scope_id=sid))
        return sorted(approved)

    # ── Refinement ──────────────────────────────────────────────────

    def refine(self, request: RefinementRequest) -> set[str]:
        """
        Re-plan targeted scopes and invalidate downstream.
        Returns the set of scope_ids that were invalidated.
        """
        self._require_plan()
        all_invalidated: set[str] = set()

        for scope_id in request.target_scopes:
            sp = self._get_sub_plan(scope_id)
            planner = self._registry.get_planner(sp.scope_type)
            new_content = planner.plan(scope_id, self._plan)
            sp.set_content(new_content, planned_by="refinement")
            self._emit(OrchestratorEvent(
                kind=EventKind.sub_plan_planned, scope_id=scope_id,
                detail="re-planned via refinement",
            ))
            invalidated = invalidate_downstream(self._plan, scope_id)
            all_invalidated.update(invalidated)
            for inv_id in invalidated:
                self._emit(OrchestratorEvent(kind=EventKind.sub_plan_stale, scope_id=inv_id))

        self._emit(OrchestratorEvent(kind=EventKind.refinement_applied))
        return all_invalidated

    # ── Step / Run ──────────────────────────────────────────────────

    def step(self) -> StepResult:
        """
        Advance the plan by one step:

        1. Auto-approve draft sub-plans that don't need human approval.
        2. Execute all sub-plans that are ready (approved + deps done).
        3. If nothing could be done, report what's blocking.

        Returns a StepResult describing what happened.
        """
        self._require_plan()
        result = StepResult()

        if self.is_complete:
            result.complete = True
            self._emit(OrchestratorEvent(kind=EventKind.plan_complete))
            return result

        # Phase 1: Auto-approve drafts that don't need human review
        for sid, sp in self._plan.sub_plans.items():
            if sp.status == SubPlanStatus.draft and not self._policy.needs_approval(sp, self._plan):
                sp.approve()
                result.auto_approved.append(sid)
                self._emit(OrchestratorEvent(
                    kind=EventKind.sub_plan_auto_approved, scope_id=sid,
                ))

        # Phase 2: Re-plan any stale sub-plans back to draft
        for sid, sp in self._plan.sub_plans.items():
            if sp.status == SubPlanStatus.stale:
                planner = self._registry.get_planner(sp.scope_type)
                new_content = planner.plan(sid, self._plan)
                sp.set_content(new_content, planned_by="re-plan")
                self._emit(OrchestratorEvent(
                    kind=EventKind.sub_plan_planned, scope_id=sid,
                    detail="re-planned after stale",
                ))

        # Phase 3: Execute ready sub-plans
        ready = ready_to_execute(self._plan)
        for sid in ready:
            sp = self._plan.sub_plans[sid]
            sp.mark_executing()
            self._emit(OrchestratorEvent(kind=EventKind.sub_plan_executing, scope_id=sid))
            try:
                executor = self._registry.get_executor(sp.scope_type)
                exec_result = executor.execute(sp, self._plan)
                sp.mark_done(result=exec_result)
                result.executed.append(sid)
                self._emit(OrchestratorEvent(kind=EventKind.sub_plan_done, scope_id=sid))
            except Exception as exc:
                sp.mark_failed(error=str(exc))
                result.failed.append(sid)
                self._emit(OrchestratorEvent(
                    kind=EventKind.sub_plan_failed, scope_id=sid, detail=str(exc),
                ))

        # Phase 4: Check completion
        if self.is_complete:
            result.complete = True
            self._emit(OrchestratorEvent(kind=EventKind.plan_complete))
            return result

        # Phase 5: Report what's blocking
        result.awaiting_approval = self.pending_approval
        if not result.executed and not result.auto_approved and not result.awaiting_approval:
            result.no_progress = True
            self._emit(OrchestratorEvent(kind=EventKind.step_no_progress))

        return result

    def run(self, max_steps: int = 50) -> StepResult:
        """
        Drive the plan to completion by calling step() repeatedly.

        Stops when:
        - Plan is complete
        - Human approval is needed (awaiting_approval is non-empty)
        - No progress can be made
        - max_steps reached

        Returns the last StepResult.
        """
        self._require_plan()
        last_result = StepResult()
        for _ in range(max_steps):
            last_result = self.step()
            if last_result.complete:
                break
            if last_result.awaiting_approval:
                break
            if last_result.no_progress:
                break
        return last_result

    # ── Internal helpers ────────────────────────────────────────────

    def _require_plan(self) -> None:
        if self._plan is None:
            raise RuntimeError("No plan loaded. Call load_plan() or propose() first.")

    def _get_sub_plan(self, scope_id: str):
        sp = self._plan.get(scope_id)
        if sp is None:
            raise KeyError(f"Sub-plan '{scope_id}' not found in plan.")
        return sp

    def _emit(self, event: OrchestratorEvent) -> None:
        logger.debug("[Orchestrator] %s scope=%s %s", event.kind.value, event.scope_id, event.detail or "")
        if self._on_event:
            self._on_event(event)
