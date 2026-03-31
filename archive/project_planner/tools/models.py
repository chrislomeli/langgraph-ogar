"""
Pydantic input/output models for the high-level tool handlers.

These are the contracts an LLM agent would see — simple, flat, descriptive.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── plan_task ──────────────────────────────────────────────────────


class PlanTaskInput(BaseModel):
    """Create a task, optionally link it to a milestone, and assign it."""
    project_id: str = Field(description="Project to add the task to")
    title: str = Field(description="Short title for the task")
    description: Optional[str] = Field(default=None, description="Longer description with context")
    kind: str = Field(default="task", description="task | milestone | research | decision | chore")
    milestone_id: Optional[str] = Field(default=None, description="Milestone this task contributes to")
    depends_on: list[str] = Field(default_factory=list, description="IDs of tasks this depends on")
    assign_to: Optional[str] = Field(default=None, description="Actor ID to assign to")
    priority: Optional[int] = Field(default=None, description="Priority (higher = more important)")
    actor_id: str = Field(description="Who is performing this action")


class PlanTaskOutput(BaseModel):
    """Result of creating a task."""
    work_item_id: str
    title: str
    linked_to_milestone: Optional[str] = None
    dependencies: list[str] = Field(default_factory=list)
    assigned_to: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


# ── update_status ──────────────────────────────────────────────────


class UpdateStatusInput(BaseModel):
    """Change the state of a work item or outcome."""
    item_id: str = Field(description="ID of the work item or outcome")
    new_state: str = Field(description="New state: proposed | planned | active | done | canceled (work items) or pending | verified | failed | waived (outcomes)")
    actor_id: str = Field(description="Who is performing this action")
    reason: Optional[str] = Field(default=None, description="Why the state is changing")


class UpdateStatusOutput(BaseModel):
    """Result of a status change."""
    item_id: str
    old_state: str
    new_state: str
    warnings: list[str] = Field(default_factory=list, description="Policy warnings (e.g. undone children)")


# ── get_context ────────────────────────────────────────────────────


class GetContextInput(BaseModel):
    """Get the current state of a project — milestones, outcomes, blockers."""
    project_id: str = Field(description="Project to get context for")


class MilestoneSummary(BaseModel):
    id: str
    title: str
    state: str
    total_tasks: int
    done_tasks: int
    completion_pct: float
    is_at_risk: bool = False


class OutcomeSummary(BaseModel):
    id: str
    title: str
    state: str


class BlockerSummary(BaseModel):
    item_id: str
    item_title: str
    blocked_by: list[str]


class GetContextOutput(BaseModel):
    """Project context for an agent."""
    project_id: str
    project_name: str
    phase: str = Field(default="exploring", description="Current workflow phase: exploring | planning | executing | reviewing")
    milestones: list[MilestoneSummary] = Field(default_factory=list)
    outcomes: list[OutcomeSummary] = Field(default_factory=list)
    blockers: list[BlockerSummary] = Field(default_factory=list)
    orphan_tasks: list[str] = Field(default_factory=list, description="Task IDs not linked to any milestone")


# ── get_next_actions ───────────────────────────────────────────────


class GetNextActionsInput(BaseModel):
    """Get actionable tasks for an actor — not blocked, assigned, active/planned."""
    actor_id: str = Field(description="Actor to get next actions for")


class ActionItem(BaseModel):
    id: str
    project_id: str
    title: str
    kind: str
    state: str
    priority: Optional[int] = None
    is_blocked: bool = False


class GetNextActionsOutput(BaseModel):
    """Actionable task list for an agent or human."""
    actor_id: str
    actions: list[ActionItem] = Field(default_factory=list)
    blocked: list[ActionItem] = Field(default_factory=list, description="Assigned but blocked items, for awareness")


# ── add_finding ────────────────────────────────────────────────────


class AddFindingInput(BaseModel):
    """Record a note or artifact against a work item."""
    target_id: str = Field(description="Work item or outcome to attach to")
    project_id: str = Field(description="Project ID for scoping")
    actor_id: str = Field(description="Who is recording this")
    note: Optional[str] = Field(default=None, description="Free-text note body")
    tags: list[str] = Field(default_factory=list, description="Tags for the note")
    artifact_ref: Optional[str] = Field(default=None, description="URL or path to an artifact")
    artifact_kind: Optional[str] = Field(default=None, description="doc | repo | file | url | pr | build | design")


class AddFindingOutput(BaseModel):
    """Result of recording a finding."""
    note_id: Optional[str] = None
    artifact_id: Optional[str] = None
    attached_to: str


# ── set_phase ─────────────────────────────────────────────────────


class SetPhaseInput(BaseModel):
    """Advance the project workflow phase."""
    project_id: str = Field(description="Project to change phase for")
    phase: str = Field(description="exploring | planning | executing | reviewing")
    actor_id: str = Field(description="Who is performing this action")


class SetPhaseOutput(BaseModel):
    """Result of a phase change."""
    project_id: str
    old_phase: str
    new_phase: str


# ── propose_plan ──────────────────────────────────────────────────


class ProposedItem(BaseModel):
    """A single item in a proposed plan."""
    title: str = Field(description="Short title")
    description: Optional[str] = Field(default=None, description="Longer description")
    kind: str = Field(default="task", description="task | milestone | research | decision | chore")
    milestone_id: Optional[str] = Field(default=None, description="Milestone this contributes to")
    depends_on_index: Optional[int] = Field(default=None, description="Index (0-based) of another item in this batch that this depends on")
    priority: Optional[int] = Field(default=None, description="Priority (higher = more important)")


class ProposePlanInput(BaseModel):
    """Propose multiple work items in 'proposed' state for human review."""
    project_id: str = Field(description="Project to add items to")
    actor_id: str = Field(description="Who is proposing")
    items: list[ProposedItem] = Field(description="Items to propose")


class ProposedItemResult(BaseModel):
    """Result for a single proposed item."""
    work_item_id: str
    title: str
    state: str = "proposed"
    warnings: list[str] = Field(default_factory=list)


class ProposePlanOutput(BaseModel):
    """Result of proposing a plan."""
    project_id: str
    items: list[ProposedItemResult] = Field(default_factory=list)
    total_proposed: int = 0


# ── approve_plan ──────────────────────────────────────────────────


class ApprovePlanInput(BaseModel):
    """Approve proposed items — promote them to 'planned' state."""
    project_id: str = Field(description="Project to approve items in")
    actor_id: str = Field(description="Who is approving")
    item_ids: Optional[list[str]] = Field(default=None, description="Specific item IDs to approve. If None, approves all proposed items.")
    assign_to: Optional[str] = Field(default=None, description="Actor to assign approved items to")


class ApprovePlanOutput(BaseModel):
    """Result of approving proposed items."""
    project_id: str
    approved_ids: list[str] = Field(default_factory=list)
    total_approved: int = 0
