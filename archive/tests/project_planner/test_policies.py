"""
Integration tests for Layer 2 facade policies.

Requires a running Memgraph instance.
"""

from __future__ import annotations

import json

from archive.tests.project_planner.conftest import requires_memgraph
from project_planner.persistence import commands, queries
from project_planner.facade import policies


@requires_memgraph
class TestCheckIsBlocked:

    def test_blocked_when_dep_not_done(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="blocker", project_id="p1", title="Blocker", kind="task", actor_id=actor_id, state="active")
        commands.link_depends_on(db, from_id="t1", to_id="blocker", actor_id=actor_id)

        assert policies.check_is_blocked(db, "t1") is True

    def test_not_blocked_when_dep_done(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="dep", project_id="p1", title="Dep", kind="task", actor_id=actor_id, state="done")
        commands.link_depends_on(db, from_id="t1", to_id="dep", actor_id=actor_id)

        assert policies.check_is_blocked(db, "t1") is False

    def test_not_blocked_when_no_deps(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id)

        assert policies.check_is_blocked(db, "t1") is False


@requires_memgraph
class TestCheckCanComplete:

    def test_no_warnings_when_clean(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="t1", project_id="p1", title="T1", kind="task", actor_id=actor_id)

        warnings = policies.check_can_complete(db, "t1")
        assert warnings == []

    def test_warns_undone_children(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="parent", project_id="p1", title="Parent", kind="milestone", actor_id=actor_id)
        commands.create_work_item(db, id="child", project_id="p1", title="Child", kind="task", actor_id=actor_id, state="active")
        commands.link_parent(db, child_id="child", parent_id="parent", actor_id=actor_id)

        warnings = policies.check_can_complete(db, "parent")
        codes = [w.code for w in warnings]
        assert "undone_child" in codes

    def test_warns_unverified_acceptance(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        acc = json.dumps({"description": "Tests pass", "verified": False})
        commands.create_work_item(
            db, id="t1", project_id="p1", title="T1", kind="task",
            actor_id=actor_id, acceptance={"description": "Tests pass", "verified": False},
        )

        warnings = policies.check_can_complete(db, "t1")
        codes = [w.code for w in warnings]
        assert "acceptance_not_verified" in codes

    def test_warns_pending_outcome(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="m1", project_id="p1", title="M", kind="milestone", actor_id=actor_id)
        commands.create_outcome(db, id="o1", project_id="p1", title="O", criteria="C", actor_id=actor_id)
        commands.link_contributes(db, from_id="m1", to_id="o1", actor_id=actor_id)

        warnings = policies.check_can_complete(db, "m1")
        codes = [w.code for w in warnings]
        assert "outcome_pending" in codes


@requires_memgraph
class TestCheckOrphanTasks:

    def test_finds_orphans(self, db, actor_id):
        commands.create_project(db, id="p1", name="P", actor_id=actor_id)
        commands.create_work_item(db, id="orphan", project_id="p1", title="Orphan", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="connected", project_id="p1", title="Connected", kind="task", actor_id=actor_id)
        commands.create_work_item(db, id="m1", project_id="p1", title="M", kind="milestone", actor_id=actor_id)
        commands.link_contributes(db, from_id="connected", to_id="m1", actor_id=actor_id)

        warnings = policies.check_orphan_tasks(db, "p1")
        orphan_ids = [w.work_item_id for w in warnings]
        assert "orphan" in orphan_ids
        assert "connected" not in orphan_ids
