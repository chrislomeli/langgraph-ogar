"""
Plan models — SubPlan, PlanGraph, and supporting types.

These are the core data structures for the plan framework.
Domain-agnostic: the framework never inspects sub-plan content.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ── Status & Phase Enums ────────────────────────────────────────────


class SubPlanStatus(str, Enum):
    """Lifecycle states for a sub-plan node."""

    draft = "draft"
    approved = "approved"
    locked = "locked"
    stale = "stale"
    executing = "executing"
    done = "done"
    failed = "failed"


class PlanPhase(str, Enum):
    """High-level phase of the overall plan."""

    proposing = "proposing"
    reviewing = "reviewing"
    executing = "executing"
    refining = "refining"
    complete = "complete"


# ── SubPlan ─────────────────────────────────────────────────────────


class SubPlan(BaseModel):
    """
    A single node in the plan DAG.

    Generic over content: the framework stores it as ``Any`` and never
    inspects it.  Domain code is responsible for interpreting content
    and result payloads.
    """

    model_config = {"frozen": False}

    scope_id: str = Field(
        ...,
        description="Unique identifier within the plan, e.g. 'harmony', 'compile'.",
    )
    scope_type: str = Field(
        ...,
        description="Type tag for routing to the correct engine/executor.",
    )
    status: SubPlanStatus = SubPlanStatus.draft
    version: int = Field(default=1, ge=1)

    content: Optional[Any] = Field(
        default=None,
        description="Domain-specific payload (None until planned).",
    )
    result: Optional[Any] = Field(
        default=None,
        description="Execution result (None until done).",
    )

    condition: Optional[str] = Field(
        default=None,
        description="Human-readable condition for inclusion, e.g. 'only if feel is latin'.",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    planned_by: Optional[str] = Field(
        default=None,
        description="Who/what produced the content, e.g. 'deterministic_planner', 'gpt-4'.",
    )

    def touch(self) -> None:
        """Update the timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def set_content(self, content: Any, planned_by: str) -> None:
        """Set new content, bump version, reset to draft."""
        self.content = content
        self.planned_by = planned_by
        self.version += 1
        self.status = SubPlanStatus.draft
        self.result = None
        self.touch()

    def approve(self) -> None:
        """Transition draft → approved."""
        if self.status not in (SubPlanStatus.draft,):
            raise InvalidTransitionError(self.scope_id, self.status, SubPlanStatus.approved)
        self.status = SubPlanStatus.approved
        self.touch()

    def lock(self) -> None:
        """Transition approved|done → locked."""
        if self.status not in (SubPlanStatus.approved, SubPlanStatus.done):
            raise InvalidTransitionError(self.scope_id, self.status, SubPlanStatus.locked)
        self.status = SubPlanStatus.locked
        self.touch()

    def mark_executing(self) -> None:
        """Transition approved → executing."""
        if self.status not in (SubPlanStatus.approved,):
            raise InvalidTransitionError(self.scope_id, self.status, SubPlanStatus.executing)
        self.status = SubPlanStatus.executing
        self.touch()

    def mark_done(self, result: Any = None) -> None:
        """Transition executing → done."""
        if self.status not in (SubPlanStatus.executing,):
            raise InvalidTransitionError(self.scope_id, self.status, SubPlanStatus.done)
        self.status = SubPlanStatus.done
        self.result = result
        self.touch()

    def mark_failed(self, error: Optional[str] = None) -> None:
        """Transition executing → failed."""
        if self.status not in (SubPlanStatus.executing,):
            raise InvalidTransitionError(self.scope_id, self.status, SubPlanStatus.failed)
        self.status = SubPlanStatus.failed
        self.result = {"error": error} if error else None
        self.touch()

    def mark_stale(self) -> None:
        """Transition done|approved → stale.  Locked sub-plans are immune."""
        if self.status == SubPlanStatus.locked:
            return  # locked survives invalidation
        if self.status not in (SubPlanStatus.done, SubPlanStatus.approved):
            raise InvalidTransitionError(self.scope_id, self.status, SubPlanStatus.stale)
        self.status = SubPlanStatus.stale
        self.touch()


# ── PlanGraph ───────────────────────────────────────────────────────


class PlanGraph(BaseModel):
    """
    A directed acyclic graph of sub-plans.

    Invariants enforced at construction and after every mutation:
    - No cycles
    - Every dependency target exists
    - scope_ids are unique
    """

    model_config = {"frozen": False}

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    sub_plans: dict[str, SubPlan] = Field(default_factory=dict)
    dependencies: dict[str, set[str]] = Field(default_factory=dict)
    intent_summary: Optional[str] = None

    parent_plan_id: Optional[str] = None
    version: int = Field(default=1, ge=1)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _validate_graph(self) -> "PlanGraph":
        # Every dependency target must exist
        for scope_id, deps in self.dependencies.items():
            if scope_id not in self.sub_plans:
                raise ValueError(
                    f"Dependency source '{scope_id}' is not a known sub-plan."
                )
            for dep in deps:
                if dep not in self.sub_plans:
                    raise ValueError(
                        f"Sub-plan '{scope_id}' depends on unknown '{dep}'."
                    )
                if dep == scope_id:
                    raise ValueError(
                        f"Sub-plan '{scope_id}' cannot depend on itself."
                    )
        # Cycle detection (import here to avoid circular import at module level)
        from framework.langgraph_ext.planning.dag import topological_sort, CycleError

        try:
            topological_sort(self)
        except CycleError as exc:
            raise ValueError(str(exc)) from exc
        return self

    # ── Mutation helpers ────────────────────────────────────────────

    def add_sub_plan(
        self,
        sub_plan: SubPlan,
        depends_on: Optional[set[str]] = None,
    ) -> None:
        """Add a sub-plan to the graph.  Validates acyclicity."""
        if sub_plan.scope_id in self.sub_plans:
            raise ValueError(f"Sub-plan '{sub_plan.scope_id}' already exists.")
        deps = depends_on or set()
        for dep in deps:
            if dep not in self.sub_plans:
                raise ValueError(
                    f"Dependency '{dep}' does not exist in the plan."
                )
        # Tentatively add, then validate
        self.sub_plans[sub_plan.scope_id] = sub_plan
        self.dependencies[sub_plan.scope_id] = deps
        try:
            self._validate_graph()
        except ValueError:
            # Roll back
            del self.sub_plans[sub_plan.scope_id]
            del self.dependencies[sub_plan.scope_id]
            raise
        self.updated_at = datetime.now(timezone.utc)

    def remove_sub_plan(self, scope_id: str) -> SubPlan:
        """Remove a sub-plan and all edges referencing it."""
        if scope_id not in self.sub_plans:
            raise KeyError(f"Sub-plan '{scope_id}' not found.")
        # Remove from other sub-plans' dependency sets
        for deps in self.dependencies.values():
            deps.discard(scope_id)
        sp = self.sub_plans.pop(scope_id)
        self.dependencies.pop(scope_id, None)
        self.updated_at = datetime.now(timezone.utc)
        return sp

    def add_dependency(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge.  Validates acyclicity."""
        if from_id not in self.sub_plans:
            raise KeyError(f"Sub-plan '{from_id}' not found.")
        if to_id not in self.sub_plans:
            raise KeyError(f"Sub-plan '{to_id}' not found.")
        if from_id == to_id:
            raise ValueError(f"Sub-plan '{from_id}' cannot depend on itself.")
        deps = self.dependencies.setdefault(from_id, set())
        deps.add(to_id)
        try:
            self._validate_graph()
        except ValueError:
            deps.discard(to_id)
            raise
        self.updated_at = datetime.now(timezone.utc)

    def get(self, scope_id: str) -> Optional[SubPlan]:
        """Get a sub-plan by scope_id, or None."""
        return self.sub_plans.get(scope_id)

    def all_leaves_done(self) -> bool:
        """True if every leaf sub-plan has status done or locked."""
        from framework.langgraph_ext.planning.dag import leaves

        for lid in leaves(self):
            sp = self.sub_plans[lid]
            if sp.status not in (SubPlanStatus.done, SubPlanStatus.locked):
                return False
        return True


# ── RefinementRequest ───────────────────────────────────────────────


class RefinementRequest(BaseModel):
    """A request to modify part of an existing plan."""

    model_config = {"frozen": True}

    prompt: str = Field(
        ...,
        description="What the user wants changed.",
    )
    target_scopes: frozenset[str] = Field(
        default_factory=frozenset,
        description="Hint: which sub-plans are affected (empty = auto-detect).",
    )
    source_plan_id: Optional[str] = Field(
        default=None,
        description="The plan being refined.",
    )


# ── Errors ──────────────────────────────────────────────────────────


class InvalidTransitionError(Exception):
    """Raised when a sub-plan status transition is not allowed."""

    def __init__(
        self,
        scope_id: str,
        from_status: SubPlanStatus,
        to_status: SubPlanStatus,
    ) -> None:
        self.scope_id = scope_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid transition for '{scope_id}': {from_status.value} → {to_status.value}"
        )
