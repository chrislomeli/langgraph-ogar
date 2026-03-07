"""
Integration tests for Layer 1 write commands.

Requires a running Memgraph instance.
"""

from __future__ import annotations

import pytest

from tests.project_planner.conftest import requires_memgraph
from project_planner.persistence import commands, queries


@requires_memgraph
class TestCreateProject:

    def test_create_project(self, db, actor_id):
        pid = commands.create_project(db, id="proj_1", name="Demo", actor_id=actor_id)
        assert pid == "proj_1"
        proj = queries.get_project(db, "proj_1")
        assert proj is not None
        assert proj["name"] == "Demo"
        assert proj["status"] == "active"

    def test_create_project_auto_id(self, db, actor_id):
        pid = commands.create_project(db, name="Auto", actor_id=actor_id)
        assert pid  # non-empty
        proj = queries.get_project(db, pid)
        assert proj["name"] == "Auto"


@requires_memgraph
class TestCreateWorkItem:

    def test_create_minimal(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        wi_id = commands.create_work_item(
            db, id="wi_1", project_id="p1", title="Task 1",
            kind="task", actor_id=actor_id,
        )
        assert wi_id == "wi_1"
        wi = queries.get_work_item(db, "wi_1")
        assert wi["title"] == "Task 1"
        assert wi["state"] == "proposed"
        assert wi["kind"] == "task"

    def test_create_with_all_fields(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(
            db, id="wi_full", project_id="p1", title="Full",
            kind="milestone", actor_id=actor_id,
            description="A detailed description",
            state="active", priority=80,
            estimate_minutes=120,
            acceptance={"description": "Tests pass", "verified": False},
        )
        wi = queries.get_work_item(db, "wi_full")
        assert wi["description"] == "A detailed description"
        assert wi["priority"] == 80
        assert wi["estimate_minutes"] == 120


@requires_memgraph
class TestSetWorkItemState:

    def test_state_change(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(
            db, id="wi_1", project_id="p1", title="T",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.set_work_item_state(
            db, id="wi_1", new_state="done", actor_id=actor_id,
        )
        wi = queries.get_work_item(db, "wi_1")
        assert wi["state"] == "done"

    def test_state_change_missing_raises(self, db, actor_id):
        with pytest.raises(KeyError, match="not found"):
            commands.set_work_item_state(
                db, id="nonexistent", new_state="done", actor_id=actor_id,
            )

    def test_state_change_emits_event(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(
            db, id="wi_1", project_id="p1", title="T",
            kind="task", actor_id=actor_id, state="active",
        )
        commands.set_work_item_state(
            db, id="wi_1", new_state="done", actor_id=actor_id,
        )
        events = queries.get_events(db, target_id="wi_1", verb="WorkItemStateChanged")
        assert len(events) >= 1


@requires_memgraph
class TestUpdateWorkItem:

    def test_update_fields(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(
            db, id="wi_1", project_id="p1", title="Old",
            kind="task", actor_id=actor_id,
        )
        commands.update_work_item(db, id="wi_1", actor_id=actor_id, title="New", priority=99)
        wi = queries.get_work_item(db, "wi_1")
        assert wi["title"] == "New"
        assert wi["priority"] == 99


@requires_memgraph
class TestLinkParent:

    def test_link_and_query(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="parent", project_id="p1", title="Parent", kind="milestone", actor_id=actor_id)
        commands.create_work_item(db, id="child", project_id="p1", title="Child", kind="task", actor_id=actor_id)
        commands.link_parent(db, child_id="child", parent_id="parent", actor_id=actor_id)

        children = queries.get_children(db, "parent")
        assert len(children) == 1
        assert children[0]["id"] == "child"

        parent = queries.get_parent(db, "child")
        assert parent is not None
        assert parent["id"] == "parent"

    def test_rejects_self_link(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="wi", project_id="p1", title="T", kind="task", actor_id=actor_id)
        with pytest.raises(ValueError, match="own parent"):
            commands.link_parent(db, child_id="wi", parent_id="wi", actor_id=actor_id)

    def test_rejects_cycle(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="a", project_id="p1", title="A", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="b", project_id="p1", title="B", kind="task", actor_id=actor_id)
        commands.link_parent(db, child_id="b", parent_id="a", actor_id=actor_id)
        with pytest.raises(ValueError, match="cycle"):
            commands.link_parent(db, child_id="a", parent_id="b", actor_id=actor_id)

    def test_rejects_cross_project(self, db, actor_id):
        commands.create_project(db, id="p1", name="P1", actor_id=actor_id)
        commands.create_project(db, id="p2", name="P2", actor_id=actor_id)
        commands.create_work_item(db, id="wi_p1", project_id="p1", title="T1", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="wi_p2", project_id="p2", title="T2", kind="task", actor_id=actor_id)
        with pytest.raises(ValueError, match="project"):
            commands.link_parent(db, child_id="wi_p2", parent_id="wi_p1", actor_id=actor_id)

    def test_unlink(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="parent", project_id="p1", title="Parent", kind="milestone", actor_id=actor_id)
        commands.create_work_item(db, id="child", project_id="p1", title="Child", kind="task", actor_id=actor_id)
        commands.link_parent(db, child_id="child", parent_id="parent", actor_id=actor_id)
        commands.unlink_parent(db, child_id="child", parent_id="parent", actor_id=actor_id)
        assert queries.get_children(db, "parent") == []


@requires_memgraph
class TestLinkContributes:

    def test_link_and_query(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="task", project_id="p1", title="Task", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="milestone", project_id="p1", title="Milestone", kind="milestone", actor_id=actor_id)
        commands.link_contributes(db, from_id="task", to_id="milestone", actor_id=actor_id)

        contributors = queries.get_contributors(db, "milestone")
        assert len(contributors) == 1
        assert contributors[0]["id"] == "task"

    def test_rejects_cross_project(self, db, actor_id):
        commands.create_project(db, id="p1", name="P1", actor_id=actor_id)
        commands.create_project(db, id="p2", name="P2", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="m2", project_id="p2", title="M2", kind="milestone", actor_id=actor_id)
        with pytest.raises(ValueError, match="project"):
            commands.link_contributes(db, from_id="t1", to_id="m2", actor_id=actor_id)

    def test_contributes_to_outcome(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="m1", project_id="p1", title="M", kind="milestone", actor_id=actor_id)
        commands.create_outcome(db, id="o1", project_id="p1", title="O", criteria="Done", actor_id=actor_id)
        commands.link_contributes(db, from_id="m1", to_id="o1", actor_id=actor_id)

        targets = queries.get_contributes_to(db, "m1")
        assert len(targets) == 1
        assert targets[0]["id"] == "o1"


@requires_memgraph
class TestLinkDependsOn:

    def test_link_and_query(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="a", project_id="p1", title="A", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="b", project_id="p1", title="B", kind="task", actor_id=actor_id)
        commands.link_depends_on(db, from_id="a", to_id="b", actor_id=actor_id)

        deps = queries.get_dependencies(db, "a")
        assert len(deps) == 1
        assert deps[0]["id"] == "b"

        dependents = queries.get_dependents(db, "b")
        assert len(dependents) == 1
        assert dependents[0]["id"] == "a"

    def test_rejects_cycle(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="a", project_id="p1", title="A", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="b", project_id="p1", title="B", kind="task", actor_id=actor_id)
        commands.link_depends_on(db, from_id="a", to_id="b", actor_id=actor_id)
        with pytest.raises(ValueError, match="cycle"):
            commands.link_depends_on(db, from_id="b", to_id="a", actor_id=actor_id)

    def test_allows_cross_project(self, db, actor_id):
        commands.create_project(db, id="p1", name="P1", actor_id=actor_id)
        commands.create_project(db, id="p2", name="P2", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="t2", project_id="p2", title="T2", kind="task", actor_id=actor_id)
        commands.link_depends_on(db, from_id="t1", to_id="t2", actor_id=actor_id)
        deps = queries.get_dependencies(db, "t1")
        assert len(deps) == 1


@requires_memgraph
class TestAssignment:

    def test_assign_and_query(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="wi", project_id="p1", title="T", kind="task", actor_id=actor_id)
        commands.assign(db, work_item_id="wi", actor_id=actor_id, assigned_by=actor_id)

        actors = queries.get_assignments(db, "wi")
        assert len(actors) == 1
        assert actors[0]["id"] == actor_id

        items = queries.get_assigned_items(db, actor_id)
        assert any(i["id"] == "wi" for i in items)

    def test_multiple_assignments(self, db, actor_id):
        agent_id = commands.create_actor(db, id="agent_1", kind="agent", name="Bot")
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="wi", project_id="p1", title="T", kind="task", actor_id=actor_id)
        commands.assign(db, work_item_id="wi", actor_id=actor_id, assigned_by=actor_id)
        commands.assign(db, work_item_id="wi", actor_id=agent_id, assigned_by=actor_id)

        actors = queries.get_assignments(db, "wi")
        assert len(actors) == 2

    def test_unassign(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="wi", project_id="p1", title="T", kind="task", actor_id=actor_id)
        commands.assign(db, work_item_id="wi", actor_id=actor_id, assigned_by=actor_id)
        commands.unassign(db, work_item_id="wi", actor_id=actor_id, unassigned_by=actor_id)
        assert queries.get_assignments(db, "wi") == []


@requires_memgraph
class TestOutcome:

    def test_create_and_query(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        oid = commands.create_outcome(
            db, id="o1", project_id="p1", title="API works",
            criteria="CRUD tests pass", actor_id=actor_id,
        )
        assert oid == "o1"
        o = queries.get_outcome(db, "o1")
        assert o["state"] == "pending"

    def test_set_state(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_outcome(db, id="o1", project_id="p1", title="O", criteria="C", actor_id=actor_id)
        commands.set_outcome_state(db, id="o1", new_state="verified", actor_id=actor_id)
        o = queries.get_outcome(db, "o1")
        assert o["state"] == "verified"


@requires_memgraph
class TestAttachments:

    def test_add_note(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="wi", project_id="p1", title="T", kind="task", actor_id=actor_id)
        nid = commands.add_note(db, target_id="wi", project_id="p1", body="Remember this", actor_id=actor_id, tags=["important"])
        assert nid

        notes = queries.get_notes(db, "wi")
        assert len(notes) == 1
        assert notes[0]["body"] == "Remember this"
        assert notes[0]["project_id"] == "p1"

    def test_attach_artifact(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="wi", project_id="p1", title="T", kind="task", actor_id=actor_id)
        aid = commands.attach_artifact(db, target_id="wi", project_id="p1", kind="doc", ref="/docs/api.md", actor_id=actor_id)
        assert aid

        artifacts = queries.get_artifacts(db, "wi")
        assert len(artifacts) == 1
        assert artifacts[0]["ref"] == "/docs/api.md"
        assert artifacts[0]["project_id"] == "p1"


@requires_memgraph
class TestProjectRoot:

    def test_set_root_and_plan_tree(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="root", project_id="p1", title="Root", kind="milestone", actor_id=actor_id)
        commands.create_work_item(db, id="child", project_id="p1", title="Child", kind="task", actor_id=actor_id)
        commands.set_project_root(db, project_id="p1", work_item_id="root", actor_id=actor_id)
        commands.link_parent(db, child_id="child", parent_id="root", actor_id=actor_id)

        tree = queries.get_plan_tree(db, "p1")
        assert len(tree) == 2
        ids = [n["id"] for n in tree]
        assert "root" in ids
        assert "child" in ids


@requires_memgraph
class TestEventLog:

    def test_events_created_for_commands(self, db, actor_id):
        pid = commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        events = queries.get_events(db, target_id="p1")
        assert len(events) >= 1
        assert events[0]["verb"] == "ProjectCreated"
        assert events[0]["actor_id"] == actor_id
