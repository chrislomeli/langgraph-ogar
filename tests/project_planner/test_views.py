"""
Integration tests for Layer 2 facade views.

Requires a running Memgraph instance.
"""

from __future__ import annotations

import pytest

from tests.project_planner.conftest import requires_memgraph
from project_planner.persistence import commands, queries
from project_planner.facade import views


@requires_memgraph
class TestMilestoneRollup:

    def test_rollup_with_contributors(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="m1", project_id="p1", title="Milestone", kind="milestone", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id, state="done")
        commands.create_work_item(db, id="t2", project_id="p1", title="T2", kind="task", actor_id=actor_id, state="active")
        commands.create_work_item(db, id="t3", project_id="p1", title="T3", kind="task", actor_id=actor_id, state="done")
        commands.link_contributes(db, from_id="t1", to_id="m1", actor_id=actor_id)
        commands.link_contributes(db, from_id="t2", to_id="m1", actor_id=actor_id)
        commands.link_contributes(db, from_id="t3", to_id="m1", actor_id=actor_id)

        rollup = views.milestone_rollup(db, "m1")
        assert rollup["total"] == 3
        assert rollup["done"] == 2
        assert rollup["completion_ratio"] == pytest.approx(2 / 3)

    def test_rollup_no_contributors(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="m1", project_id="p1", title="M", kind="milestone", actor_id=actor_id)

        rollup = views.milestone_rollup(db, "m1")
        assert rollup["total"] == 0
        assert rollup["completion_ratio"] == 0.0

    def test_rollup_missing_raises(self, db, actor_id):
        with pytest.raises(KeyError, match="not found"):
            views.milestone_rollup(db, "nonexistent")


@requires_memgraph
class TestProjectStatus:

    def test_status_report(self, db, actor_id):
        commands.create_project(db, id="p1", name="Demo", actor_id=actor_id)
        commands.create_work_item(db, id="m1", project_id="p1", title="Schema", kind="milestone", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id, state="done")
        commands.link_contributes(db, from_id="t1", to_id="m1", actor_id=actor_id)
        commands.create_outcome(db, id="o1", project_id="p1", title="API works", criteria="Tests pass", actor_id=actor_id)

        status = views.project_status(db, "p1")
        assert status["project_name"] == "Demo"
        assert len(status["milestones"]) == 1
        assert status["milestones"][0]["completion_ratio"] == 1.0
        assert len(status["outcomes"]) == 1
        assert status["outcomes"][0]["state"] == "pending"


@requires_memgraph
class TestGtdNextActions:

    def test_excludes_blocked_items(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="Unblocked", kind="task", actor_id=actor_id, state="active")
        commands.create_work_item(db, id="t2", project_id="p1", title="Blocked", kind="task", actor_id=actor_id, state="active")
        commands.create_work_item(db, id="blocker", project_id="p1", title="Blocker", kind="task", actor_id=actor_id, state="active")
        commands.link_depends_on(db, from_id="t2", to_id="blocker", actor_id=actor_id)
        commands.assign(db, work_item_id="t1", actor_id=actor_id, assigned_by=actor_id)
        commands.assign(db, work_item_id="t2", actor_id=actor_id, assigned_by=actor_id)

        actions = views.gtd_next_actions(db, actor_id)
        ids = [a["id"] for a in actions]
        assert "t1" in ids
        assert "t2" not in ids

    def test_includes_items_with_done_dependencies(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="Ready", kind="task", actor_id=actor_id, state="active")
        commands.create_work_item(db, id="dep", project_id="p1", title="Done dep", kind="task", actor_id=actor_id, state="done")
        commands.link_depends_on(db, from_id="t1", to_id="dep", actor_id=actor_id)
        commands.assign(db, work_item_id="t1", actor_id=actor_id, assigned_by=actor_id)

        actions = views.gtd_next_actions(db, actor_id)
        ids = [a["id"] for a in actions]
        assert "t1" in ids


@requires_memgraph
class TestBlockersReport:

    def test_finds_blockers(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="Blocked", kind="task", actor_id=actor_id, state="active")
        commands.create_work_item(db, id="b1", project_id="p1", title="Blocker1", kind="task", actor_id=actor_id, state="active")
        commands.create_work_item(db, id="b2", project_id="p1", title="Blocker2", kind="task", actor_id=actor_id, state="active")
        commands.link_depends_on(db, from_id="t1", to_id="b1", actor_id=actor_id)
        commands.link_depends_on(db, from_id="t1", to_id="b2", actor_id=actor_id)

        report = views.blockers_report(db, "p1")
        assert len(report) == 1
        assert report[0]["item_id"] == "t1"
        assert len(report[0]["blocked_by"]) == 2

    def test_no_blockers_when_deps_done(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T", kind="task", actor_id=actor_id, state="active")
        commands.create_work_item(db, id="dep", project_id="p1", title="Dep", kind="task", actor_id=actor_id, state="done")
        commands.link_depends_on(db, from_id="t1", to_id="dep", actor_id=actor_id)

        report = views.blockers_report(db, "p1")
        assert len(report) == 0
