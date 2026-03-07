"""
LangGraph-compatible tool definitions for the project engine.

Each tool wraps a handler from project_planner.tools.handlers,
injecting db, actor_id, and project_id so the LLM only sees
the fields it needs to reason about.
"""

from __future__ import annotations

from typing import Annotated, Optional

from gqlalchemy import Memgraph
from langchain_core.tools import tool

from project_planner.persistence import queries
from project_planner.tools.handlers import (
    add_finding,
    approve_plan,
    get_context,
    get_next_actions,
    plan_task,
    propose_plan,
    set_phase,
    update_status,
)
from project_planner.tools.models import (
    AddFindingInput,
    ApprovePlanInput,
    GetContextInput,
    GetNextActionsInput,
    PlanTaskInput,
    ProposedItem,
    ProposePlanInput,
    SetPhaseInput,
    UpdateStatusInput,
)


def build_project_tools(db: Memgraph, project_id: str, actor_id: str) -> list:
    """
    Build LangGraph tools with db/project_id/actor_id baked in.

    The LLM never sees these IDs — they're injected from graph state.
    """

    @tool
    def plan_task_tool(
        title: Annotated[str, "Short title for the task"],
        description: Annotated[Optional[str], "Longer description"] = None,
        kind: Annotated[str, "task | milestone | research | decision | chore"] = "task",
        milestone_id: Annotated[Optional[str], "Milestone this contributes to"] = None,
        depends_on: Annotated[Optional[list[str]], "IDs of tasks this depends on"] = None,
        assign_to: Annotated[Optional[str], "Actor ID to assign to"] = None,
        priority: Annotated[Optional[int], "Priority (higher = more important)"] = None,
    ) -> str:
        """Create a task in the project plan. Optionally link it to a milestone, add dependencies, and assign it. During the 'planning' phase, tasks are created in 'proposed' state for review."""
        resolved_assign = actor_id if assign_to == "self" else assign_to
        result = plan_task(db, PlanTaskInput(
            project_id=project_id,
            title=title,
            description=description,
            kind=kind,
            milestone_id=milestone_id,
            depends_on=depends_on or [],
            assign_to=resolved_assign,
            priority=priority,
            actor_id=actor_id,
        ))
        return result.model_dump_json()

    @tool
    def update_status_tool(
        item_id: Annotated[str, "ID of the work item or outcome"],
        new_state: Annotated[str, "New state: proposed | planned | active | done | canceled"],
        reason: Annotated[Optional[str], "Why the state is changing"] = None,
    ) -> str:
        """Change the state of a work item or outcome. Returns warnings if there are policy concerns."""
        result = update_status(db, UpdateStatusInput(
            item_id=item_id,
            new_state=new_state,
            actor_id=actor_id,
            reason=reason,
        ))
        return result.model_dump_json()

    @tool
    def get_context_tool() -> str:
        """Get the current project status — milestones, outcomes, blockers, and orphan tasks."""
        result = get_context(db, GetContextInput(project_id=project_id))
        return result.model_dump_json()

    @tool
    def get_next_actions_tool() -> str:
        """Get actionable tasks — assigned, not blocked. Also shows blocked items for awareness."""
        result = get_next_actions(db, GetNextActionsInput(actor_id=actor_id))
        return result.model_dump_json()

    @tool
    def add_finding_tool(
        target_id: Annotated[str, "Work item or outcome to attach to"],
        note: Annotated[Optional[str], "Free-text note body"] = None,
        tags: Annotated[Optional[list[str]], "Tags for the note"] = None,
        artifact_ref: Annotated[Optional[str], "URL or path to an artifact"] = None,
        artifact_kind: Annotated[Optional[str], "doc | repo | file | url | pr | build | design"] = None,
    ) -> str:
        """Record a note or artifact against a work item."""
        result = add_finding(db, AddFindingInput(
            target_id=target_id,
            project_id=project_id,
            actor_id=actor_id,
            note=note,
            tags=tags or [],
            artifact_ref=artifact_ref,
            artifact_kind=artifact_kind,
        ))
        return result.model_dump_json()

    @tool
    def set_phase_tool(
        phase: Annotated[str, "New phase: exploring | planning | executing | reviewing"],
    ) -> str:
        """Advance the project workflow phase. Phases: exploring -> planning -> executing -> reviewing."""
        result = set_phase(db, SetPhaseInput(
            project_id=project_id,
            phase=phase,
            actor_id=actor_id,
        ))
        return result.model_dump_json()

    @tool
    def propose_plan_tool(
        items: Annotated[list[dict], "REQUIRED list of items. Each dict: {title: str, description?: str, kind?: str, milestone_id?: str, depends_on_index?: int, priority?: int}. depends_on_index is 0-based index of an earlier item in this list."],
    ) -> str:
        """Propose multiple work items at once for human review. All items are created in 'proposed' state. You MUST provide the items list. Example: [{title: 'Design API', priority: 90}, {title: 'Implement API', depends_on_index: 0, priority: 80}]."""
        parsed_items = [ProposedItem(**item) for item in items]
        result = propose_plan(db, ProposePlanInput(
            project_id=project_id,
            actor_id=actor_id,
            items=parsed_items,
        ))
        return result.model_dump_json()

    @tool
    def approve_plan_tool(
        item_ids: Annotated[Optional[list[str]], "Specific item IDs to approve, or null to approve all proposed items"] = None,
    ) -> str:
        """Approve proposed items — promote them from 'proposed' to 'planned' state and assign them."""
        result = approve_plan(db, ApprovePlanInput(
            project_id=project_id,
            actor_id=actor_id,
            item_ids=item_ids,
            assign_to=actor_id,
        ))
        return result.model_dump_json()

    return [
        plan_task_tool, update_status_tool, get_context_tool,
        get_next_actions_tool, add_finding_tool,
        set_phase_tool, propose_plan_tool, approve_plan_tool,
    ]
