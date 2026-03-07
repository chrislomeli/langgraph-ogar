"""
High-level tool handlers for the project engine.

Each function takes a Pydantic input model and returns a Pydantic output model.
Internally they compose Layer 1 commands/queries and Layer 2 facade calls.

These are plain functions — no framework dependency.
"""

from __future__ import annotations

from gqlalchemy import Memgraph

from project_planner.persistence import commands, queries
from project_planner.facade import views, policies
from project_planner.tools.models import (
    AddFindingInput,
    AddFindingOutput,
    ActionItem,
    ApprovePlanInput,
    ApprovePlanOutput,
    BlockerSummary,
    GetContextInput,
    GetContextOutput,
    GetNextActionsInput,
    GetNextActionsOutput,
    MilestoneSummary,
    OutcomeSummary,
    PlanTaskInput,
    PlanTaskOutput,
    ProposedItemResult,
    ProposePlanInput,
    ProposePlanOutput,
    SetPhaseInput,
    SetPhaseOutput,
    UpdateStatusInput,
    UpdateStatusOutput,
)


# ── plan_task ──────────────────────────────────────────────────────


def plan_task(db: Memgraph, input: PlanTaskInput) -> PlanTaskOutput:
    """
    Create a task, optionally link it to a milestone and dependencies,
    and assign it.

    This is the primary "add work" operation for an agent.
    """
    warnings: list[str] = []

    # 1. Determine initial state based on project phase
    project = queries.get_project(db, input.project_id)
    phase = project["phase"] if project else "exploring"
    initial_state = "proposed" if phase == "planning" else "planned"

    # 2. Create the work item
    wi_id = commands.create_work_item(
        db,
        project_id=input.project_id,
        title=input.title,
        kind=input.kind,
        actor_id=input.actor_id,
        description=input.description,
        state=initial_state,
        priority=input.priority,
    )

    # 2. Link to milestone if provided
    linked_milestone = None
    if input.milestone_id:
        try:
            commands.link_contributes(
                db,
                from_id=wi_id,
                to_id=input.milestone_id,
                actor_id=input.actor_id,
            )
            linked_milestone = input.milestone_id
        except ValueError as e:
            warnings.append(f"Could not link to milestone: {e}")

    # 3. Add dependencies
    linked_deps: list[str] = []
    for dep_id in input.depends_on:
        try:
            commands.link_depends_on(
                db,
                from_id=wi_id,
                to_id=dep_id,
                actor_id=input.actor_id,
            )
            linked_deps.append(dep_id)
        except ValueError as e:
            warnings.append(f"Could not add dependency on '{dep_id}': {e}")

    # 4. Assign if requested
    assigned = None
    if input.assign_to:
        try:
            commands.assign(
                db,
                work_item_id=wi_id,
                actor_id=input.assign_to,
                assigned_by=input.actor_id,
            )
            assigned = input.assign_to
        except Exception as e:
            warnings.append(f"Could not assign to '{input.assign_to}': {e}")

    return PlanTaskOutput(
        work_item_id=wi_id,
        title=input.title,
        linked_to_milestone=linked_milestone,
        dependencies=linked_deps,
        assigned_to=assigned,
        warnings=warnings,
    )


# ── update_status ──────────────────────────────────────────────────


def update_status(db: Memgraph, input: UpdateStatusInput) -> UpdateStatusOutput:
    """
    Change the state of a work item or outcome.

    If marking a work item as done, runs policy checks and returns warnings.
    """
    warnings: list[str] = []

    # Determine if this is a WorkItem or Outcome
    wi = queries.get_work_item(db, input.item_id)
    if wi:
        old_state = wi["state"]

        # Run policy checks if completing
        if input.new_state == "done":
            policy_warnings = policies.check_can_complete(db, input.item_id)
            for w in policy_warnings:
                warnings.append(f"[{w.code}] {w.message}")

        # Check if blocked
        if input.new_state == "active" and policies.check_is_blocked(db, input.item_id):
            warnings.append("[blocked] This item has unresolved dependencies")

        commands.set_work_item_state(
            db,
            id=input.item_id,
            new_state=input.new_state,
            actor_id=input.actor_id,
            reason=input.reason,
        )
        return UpdateStatusOutput(
            item_id=input.item_id,
            old_state=old_state,
            new_state=input.new_state,
            warnings=warnings,
        )

    # Try as Outcome
    outcome = queries.get_outcome(db, input.item_id)
    if outcome:
        old_state = outcome["state"]
        commands.set_outcome_state(
            db,
            id=input.item_id,
            new_state=input.new_state,
            actor_id=input.actor_id,
        )
        return UpdateStatusOutput(
            item_id=input.item_id,
            old_state=old_state,
            new_state=input.new_state,
            warnings=warnings,
        )

    raise KeyError(f"No WorkItem or Outcome found with id '{input.item_id}'")


# ── get_context ────────────────────────────────────────────────────


def get_context(db: Memgraph, input: GetContextInput) -> GetContextOutput:
    """
    Get a full project context snapshot — milestones, outcomes, blockers,
    orphan tasks. This is what an agent reads to understand "where are we?"
    """
    # Get phase
    project = queries.get_project(db, input.project_id)
    phase = project["phase"] if project else "exploring"

    # Project status (milestones + outcomes)
    status = views.project_status(db, input.project_id)

    milestone_summaries = []
    for m in status["milestones"]:
        milestone_summaries.append(MilestoneSummary(
            id=m["id"],
            title=m["title"],
            state=m["state"],
            total_tasks=m["total"],
            done_tasks=m["done"],
            completion_pct=round(m["completion_ratio"] * 100, 1),
        ))

    outcome_summaries = [
        OutcomeSummary(id=o["id"], title=o["title"], state=o["state"])
        for o in status["outcomes"]
    ]

    # Blockers
    blocker_rows = views.blockers_report(db, input.project_id)
    blocker_summaries = [
        BlockerSummary(
            item_id=b["item_id"],
            item_title=b["item_title"],
            blocked_by=[x["id"] if isinstance(x, dict) else x for x in b["blocked_by"]],
        )
        for b in blocker_rows
    ]

    # Orphan tasks
    orphan_warnings = policies.check_orphan_tasks(db, input.project_id)
    orphan_ids = [w.work_item_id for w in orphan_warnings if w.work_item_id]

    return GetContextOutput(
        project_id=input.project_id,
        project_name=status["project_name"],
        phase=phase,
        milestones=milestone_summaries,
        outcomes=outcome_summaries,
        blockers=blocker_summaries,
        orphan_tasks=orphan_ids,
    )


# ── get_next_actions ───────────────────────────────────────────────


def get_next_actions(db: Memgraph, input: GetNextActionsInput) -> GetNextActionsOutput:
    """
    Get actionable tasks for an actor.

    Returns two lists:
      - actions: assigned, active/planned, NOT blocked
      - blocked: assigned but blocked (for awareness)
    """
    # Get all assigned items
    assigned = queries.get_assigned_items(db, input.actor_id)

    actions: list[ActionItem] = []
    blocked: list[ActionItem] = []

    for item in assigned:
        if item["state"] not in ("planned", "active"):
            continue

        is_blocked = policies.check_is_blocked(db, item["id"])
        action = ActionItem(
            id=item["id"],
            project_id=item["project_id"],
            title=item["title"],
            kind=item["kind"],
            state=item["state"],
            priority=item.get("priority"),
            is_blocked=is_blocked,
        )

        if is_blocked:
            blocked.append(action)
        else:
            actions.append(action)

    # Sort by priority descending
    actions.sort(key=lambda a: a.priority or 0, reverse=True)
    blocked.sort(key=lambda a: a.priority or 0, reverse=True)

    return GetNextActionsOutput(
        actor_id=input.actor_id,
        actions=actions,
        blocked=blocked,
    )


# ── add_finding ────────────────────────────────────────────────────


def add_finding(db: Memgraph, input: AddFindingInput) -> AddFindingOutput:
    """
    Record a note and/or artifact against a work item.

    At least one of note or artifact_ref should be provided.
    """
    note_id = None
    artifact_id = None

    if input.note:
        note_id = commands.add_note(
            db,
            target_id=input.target_id,
            project_id=input.project_id,
            body=input.note,
            actor_id=input.actor_id,
            tags=input.tags,
        )

    if input.artifact_ref:
        artifact_id = commands.attach_artifact(
            db,
            target_id=input.target_id,
            project_id=input.project_id,
            kind=input.artifact_kind or "doc",
            ref=input.artifact_ref,
            actor_id=input.actor_id,
        )

    return AddFindingOutput(
        note_id=note_id,
        artifact_id=artifact_id,
        attached_to=input.target_id,
    )


# ── set_phase ───────────────────────────────────────────────────


def set_phase(db: Memgraph, input: SetPhaseInput) -> SetPhaseOutput:
    """
    Advance the project workflow phase.

    Phases: exploring → planning → executing → reviewing
    """
    old_phase = commands.set_project_phase(
        db,
        project_id=input.project_id,
        phase=input.phase,
        actor_id=input.actor_id,
    )
    return SetPhaseOutput(
        project_id=input.project_id,
        old_phase=old_phase,
        new_phase=input.phase,
    )


# ── propose_plan ─────────────────────────────────────────────────


def propose_plan(db: Memgraph, input: ProposePlanInput) -> ProposePlanOutput:
    """
    Create multiple work items in 'proposed' state for human review.

    Items can reference each other by index for dependencies.
    This is the batch-create tool for the planning phase.
    """
    results: list[ProposedItemResult] = []
    created_ids: list[str] = []  # index-aligned with input.items

    for i, item in enumerate(input.items):
        warnings: list[str] = []

        # Create in proposed state
        wi_id = commands.create_work_item(
            db,
            project_id=input.project_id,
            title=item.title,
            kind=item.kind,
            actor_id=input.actor_id,
            description=item.description,
            state="proposed",
            priority=item.priority,
        )
        created_ids.append(wi_id)

        # Link to milestone
        if item.milestone_id:
            try:
                commands.link_contributes(
                    db, from_id=wi_id, to_id=item.milestone_id,
                    actor_id=input.actor_id,
                )
            except ValueError as e:
                warnings.append(f"Could not link to milestone: {e}")

        # Link dependency by index
        if item.depends_on_index is not None:
            if 0 <= item.depends_on_index < len(created_ids) - 1:
                dep_id = created_ids[item.depends_on_index]
                try:
                    commands.link_depends_on(
                        db, from_id=wi_id, to_id=dep_id,
                        actor_id=input.actor_id,
                    )
                except ValueError as e:
                    warnings.append(f"Could not add dependency: {e}")
            else:
                warnings.append(
                    f"depends_on_index {item.depends_on_index} is out of range "
                    f"(only {len(created_ids) - 1} items created before this one)"
                )

        results.append(ProposedItemResult(
            work_item_id=wi_id,
            title=item.title,
            warnings=warnings,
        ))

    return ProposePlanOutput(
        project_id=input.project_id,
        items=results,
        total_proposed=len(results),
    )


# ── approve_plan ─────────────────────────────────────────────────


def approve_plan(db: Memgraph, input: ApprovePlanInput) -> ApprovePlanOutput:
    """
    Promote proposed items to 'planned' state.

    If item_ids is None, approves ALL proposed items in the project.
    Optionally assigns them to an actor.
    """
    if input.item_ids:
        # Approve specific items
        items_to_approve = input.item_ids
    else:
        # Approve all proposed items in the project
        proposed = queries.list_work_items(db, input.project_id, state="proposed")
        items_to_approve = [item["id"] for item in proposed]

    approved_ids: list[str] = []
    for item_id in items_to_approve:
        commands.set_work_item_state(
            db, id=item_id, new_state="planned",
            actor_id=input.actor_id, reason="Approved from proposal",
        )
        approved_ids.append(item_id)

        # Assign if requested
        if input.assign_to:
            try:
                commands.assign(
                    db, work_item_id=item_id,
                    actor_id=input.assign_to,
                    assigned_by=input.actor_id,
                )
            except Exception:
                pass  # assignment is best-effort

    return ApprovePlanOutput(
        project_id=input.project_id,
        approved_ids=approved_ids,
        total_approved=len(approved_ids),
    )
