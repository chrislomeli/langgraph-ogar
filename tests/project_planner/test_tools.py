"""
Integration tests for high-level tool handlers.

Requires a running Memgraph instance.
"""

from __future__ import annotations

import pytest

from tests.project_planner.conftest import requires_memgraph
from project_planner.persistence import commands, queries
from project_planner.tools.handlers import (
    add_finding,
    get_context,
    get_next_actions,
    plan_task,
    update_status,
)
from project_planner.tools.models import (
    AddFindingInput,
    GetContextInput,
    GetNextActionsInput,
    PlanTaskInput,
    UpdateStatusInput,
)


# ── Helpers ────────────────────────────────────────────────────────


def _seed_project(db, actor_id):
    """Create a project with a milestone for tests."""
    commands.create_project(db, id="p1", name="Test Project", actor_id=actor_id)
    commands.create_work_item(
        db, id="m1", project_id="p1", title="Milestone 1",
        kind="milestone", actor_id=actor_id, state="active",
    )
    commands.set_project_root(db, project_id="p1", work_item_id="m1", actor_id=actor_id)


# ── plan_task ──────────────────────────────────────────────────────


@requires_memgraph
class TestPlanTask:

    def test_create_simple_task(self, db, actor_id):
        _seed_project(db, actor_id)
        result = plan_task(db, PlanTaskInput(
            project_id="p1",
            title="Write tests",
            actor_id=actor_id,
        ))
        assert result.work_item_id
        assert result.title == "Write tests"
        assert result.warnings == []

        # Verify in DB
        wi = queries.get_work_item(db, result.work_item_id)
        assert wi["state"] == "planned"

    def test_create_task_with_milestone(self, db, actor_id):
        _seed_project(db, actor_id)
        result = plan_task(db, PlanTaskInput(
            project_id="p1",
            title="Implement API",
            milestone_id="m1",
            actor_id=actor_id,
        ))
        assert result.linked_to_milestone == "m1"

        # Verify contribution edge
        contributors = queries.get_contributors(db, "m1")
        assert any(c["id"] == result.work_item_id for c in contributors)

    def test_create_task_with_dependency(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="dep1", project_id="p1", title="Dep",
            kind="task", actor_id=actor_id,
        )
        result = plan_task(db, PlanTaskInput(
            project_id="p1",
            title="Blocked task",
            depends_on=["dep1"],
            actor_id=actor_id,
        ))
        assert result.dependencies == ["dep1"]

    def test_create_task_with_assignment(self, db, actor_id):
        _seed_project(db, actor_id)
        result = plan_task(db, PlanTaskInput(
            project_id="p1",
            title="Assigned task",
            assign_to=actor_id,
            actor_id=actor_id,
        ))
        assert result.assigned_to == actor_id

    def test_bad_milestone_gives_warning(self, db, actor_id):
        _seed_project(db, actor_id)
        # Create task in p1 but try to link to milestone in different project
        commands.create_project(db, id="p2", name="Other", actor_id=actor_id)
        commands.create_work_item(
            db, id="m_other", project_id="p2", title="Other M",
            kind="milestone", actor_id=actor_id,
        )
        result = plan_task(db, PlanTaskInput(
            project_id="p1",
            title="Cross-project attempt",
            milestone_id="m_other",
            actor_id=actor_id,
        ))
        assert result.linked_to_milestone is None
        assert len(result.warnings) == 1
        assert "project" in result.warnings[0].lower()


# ── update_status ──────────────────────────────────────────────────


@requires_memgraph
class TestUpdateStatus:

    def test_change_work_item_state(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="t1", project_id="p1", title="T",
            kind="task", actor_id=actor_id, state="active",
        )
        result = update_status(db, UpdateStatusInput(
            item_id="t1", new_state="done", actor_id=actor_id,
        ))
        assert result.old_state == "active"
        assert result.new_state == "done"

    def test_completing_with_undone_children_warns(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="parent", project_id="p1", title="Parent",
            kind="milestone", actor_id=actor_id, state="active",
        )
        commands.create_work_item(
            db, id="child", project_id="p1", title="Child",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.link_parent(db, child_id="child", parent_id="parent", actor_id=actor_id)

        result = update_status(db, UpdateStatusInput(
            item_id="parent", new_state="done", actor_id=actor_id,
        ))
        assert result.new_state == "done"
        assert any("undone_child" in w for w in result.warnings)

    def test_activating_blocked_item_warns(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="t1", project_id="p1", title="T1",
            kind="task", actor_id=actor_id, state="planned",
        )
        commands.create_work_item(
            db, id="blocker", project_id="p1", title="Blocker",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.link_depends_on(db, from_id="t1", to_id="blocker", actor_id=actor_id)

        result = update_status(db, UpdateStatusInput(
            item_id="t1", new_state="active", actor_id=actor_id,
        ))
        assert any("blocked" in w for w in result.warnings)

    def test_change_outcome_state(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_outcome(
            db, id="o1", project_id="p1", title="O",
            criteria="C", actor_id=actor_id,
        )
        result = update_status(db, UpdateStatusInput(
            item_id="o1", new_state="verified", actor_id=actor_id,
        ))
        assert result.old_state == "pending"
        assert result.new_state == "verified"

    def test_missing_item_raises(self, db, actor_id):
        with pytest.raises(KeyError, match="No WorkItem or Outcome found"):
            update_status(db, UpdateStatusInput(
                item_id="nonexistent", new_state="done", actor_id=actor_id,
            ))


# ── get_context ────────────────────────────────────────────────────


@requires_memgraph
class TestGetContext:

    def test_full_context(self, db, actor_id):
        _seed_project(db, actor_id)
        # Add tasks contributing to milestone
        commands.create_work_item(
            db, id="t1", project_id="p1", title="Done task",
            kind="task", actor_id=actor_id, state="done",
        )
        commands.create_work_item(
            db, id="t2", project_id="p1", title="Active task",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.link_contributes(db, from_id="t1", to_id="m1", actor_id=actor_id)
        commands.link_contributes(db, from_id="t2", to_id="m1", actor_id=actor_id)

        # Add an outcome
        commands.create_outcome(
            db, id="o1", project_id="p1", title="API works",
            criteria="Tests pass", actor_id=actor_id,
        )

        # Add a blocker
        commands.create_work_item(
            db, id="t3", project_id="p1", title="Blocked",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.link_depends_on(db, from_id="t3", to_id="t2", actor_id=actor_id)

        # Add an orphan
        commands.create_work_item(
            db, id="orphan", project_id="p1", title="Orphan",
            kind="task", actor_id=actor_id,
        )

        ctx = get_context(db, GetContextInput(project_id="p1"))
        assert ctx.project_name == "Test Project"
        assert len(ctx.milestones) == 1
        assert ctx.milestones[0].total_tasks == 2
        assert ctx.milestones[0].done_tasks == 1
        assert ctx.milestones[0].completion_pct == pytest.approx(50.0)
        assert len(ctx.outcomes) == 1
        assert len(ctx.blockers) >= 1
        assert "orphan" in ctx.orphan_tasks


# ── get_next_actions ───────────────────────────────────────────────


@requires_memgraph
class TestGetNextActions:

    def test_separates_actions_and_blocked(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="t1", project_id="p1", title="Ready",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.create_work_item(
            db, id="t2", project_id="p1", title="Blocked",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.create_work_item(
            db, id="blocker", project_id="p1", title="Blocker",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.link_depends_on(db, from_id="t2", to_id="blocker", actor_id=actor_id)
        commands.assign(db, work_item_id="t1", actor_id=actor_id, assigned_by=actor_id)
        commands.assign(db, work_item_id="t2", actor_id=actor_id, assigned_by=actor_id)

        result = get_next_actions(db, GetNextActionsInput(actor_id=actor_id))
        action_ids = [a.id for a in result.actions]
        blocked_ids = [b.id for b in result.blocked]
        assert "t1" in action_ids
        assert "t2" in blocked_ids

    def test_excludes_done_items(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="done_task", project_id="p1", title="Done",
            kind="task", actor_id=actor_id, state="done",
        )
        commands.assign(db, work_item_id="done_task", actor_id=actor_id, assigned_by=actor_id)

        result = get_next_actions(db, GetNextActionsInput(actor_id=actor_id))
        all_ids = [a.id for a in result.actions] + [b.id for b in result.blocked]
        assert "done_task" not in all_ids


# ── add_finding ────────────────────────────────────────────────────


@requires_memgraph
class TestAddFinding:

    def test_add_note(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="t1", project_id="p1", title="T",
            kind="task", actor_id=actor_id,
        )
        result = add_finding(db, AddFindingInput(
            target_id="t1", project_id="p1", actor_id=actor_id,
            note="Found a bug in the schema",
            tags=["bug"],
        ))
        assert result.note_id is not None
        assert result.artifact_id is None
        assert result.attached_to == "t1"

        notes = queries.get_notes(db, "t1")
        assert len(notes) == 1
        assert notes[0]["body"] == "Found a bug in the schema"

    def test_add_artifact(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="t1", project_id="p1", title="T",
            kind="task", actor_id=actor_id,
        )
        result = add_finding(db, AddFindingInput(
            target_id="t1", project_id="p1", actor_id=actor_id,
            artifact_ref="https://github.com/repo/pr/42",
            artifact_kind="pr",
        ))
        assert result.artifact_id is not None
        assert result.note_id is None

    def test_add_both(self, db, actor_id):
        _seed_project(db, actor_id)
        commands.create_work_item(
            db, id="t1", project_id="p1", title="T",
            kind="task", actor_id=actor_id,
        )
        result = add_finding(db, AddFindingInput(
            target_id="t1", project_id="p1", actor_id=actor_id,
            note="See the PR",
            artifact_ref="https://github.com/repo/pr/42",
            artifact_kind="pr",
        ))
        assert result.note_id is not None
        assert result.artifact_id is not None
