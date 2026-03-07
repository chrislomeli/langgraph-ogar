"""Tests for planning.models — SubPlan lifecycle and PlanGraph validation."""

from __future__ import annotations

import pytest

from framework.langgraph_ext.planning.models import (
    InvalidTransitionError,
    PlanGraph,
    SubPlan,
    SubPlanStatus,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _sp(scope_id: str, scope_type: str = "generic", **kwargs) -> SubPlan:
    return SubPlan(scope_id=scope_id, scope_type=scope_type, **kwargs)


def _simple_graph() -> PlanGraph:
    """A → B → C  (linear chain)."""
    return PlanGraph(
        title="test",
        sub_plans={
            "a": _sp("a"),
            "b": _sp("b"),
            "c": _sp("c"),
        },
        dependencies={
            "a": set(),
            "b": {"a"},
            "c": {"b"},
        },
    )


# ── SubPlan status transitions ──────────────────────────────────────


class TestSubPlanLifecycle:
    def test_initial_status_is_draft(self):
        sp = _sp("x")
        assert sp.status == SubPlanStatus.draft

    def test_approve_from_draft(self):
        sp = _sp("x")
        sp.approve()
        assert sp.status == SubPlanStatus.approved

    def test_approve_from_non_draft_raises(self):
        sp = _sp("x", status=SubPlanStatus.done)
        with pytest.raises(InvalidTransitionError):
            sp.approve()

    def test_lock_from_approved(self):
        sp = _sp("x")
        sp.approve()
        sp.lock()
        assert sp.status == SubPlanStatus.locked

    def test_lock_from_done(self):
        sp = _sp("x")
        sp.approve()
        sp.mark_executing()
        sp.mark_done(result="ok")
        sp.lock()
        assert sp.status == SubPlanStatus.locked

    def test_lock_from_draft_raises(self):
        sp = _sp("x")
        with pytest.raises(InvalidTransitionError):
            sp.lock()

    def test_execute_from_approved(self):
        sp = _sp("x")
        sp.approve()
        sp.mark_executing()
        assert sp.status == SubPlanStatus.executing

    def test_execute_from_draft_raises(self):
        sp = _sp("x")
        with pytest.raises(InvalidTransitionError):
            sp.mark_executing()

    def test_done_from_executing(self):
        sp = _sp("x")
        sp.approve()
        sp.mark_executing()
        sp.mark_done(result={"value": 42})
        assert sp.status == SubPlanStatus.done
        assert sp.result == {"value": 42}

    def test_done_from_draft_raises(self):
        sp = _sp("x")
        with pytest.raises(InvalidTransitionError):
            sp.mark_done()

    def test_failed_from_executing(self):
        sp = _sp("x")
        sp.approve()
        sp.mark_executing()
        sp.mark_failed(error="boom")
        assert sp.status == SubPlanStatus.failed
        assert sp.result == {"error": "boom"}

    def test_stale_from_done(self):
        sp = _sp("x")
        sp.approve()
        sp.mark_executing()
        sp.mark_done()
        sp.mark_stale()
        assert sp.status == SubPlanStatus.stale

    def test_stale_from_approved(self):
        sp = _sp("x")
        sp.approve()
        sp.mark_stale()
        assert sp.status == SubPlanStatus.stale

    def test_stale_skips_locked(self):
        sp = _sp("x")
        sp.approve()
        sp.lock()
        sp.mark_stale()  # should be a no-op
        assert sp.status == SubPlanStatus.locked

    def test_set_content_resets_to_draft(self):
        sp = _sp("x")
        sp.approve()
        sp.mark_executing()
        sp.mark_done(result="old")
        sp.set_content({"new": True}, planned_by="test")
        assert sp.status == SubPlanStatus.draft
        assert sp.content == {"new": True}
        assert sp.result is None
        assert sp.version == 2

    def test_set_content_increments_version(self):
        sp = _sp("x")
        sp.set_content("v2", planned_by="a")
        sp.set_content("v3", planned_by="b")
        assert sp.version == 3


# ── PlanGraph construction ──────────────────────────────────────────


class TestPlanGraphConstruction:
    def test_empty_graph(self):
        g = PlanGraph(title="empty")
        assert len(g.sub_plans) == 0

    def test_simple_chain(self):
        g = _simple_graph()
        assert set(g.sub_plans.keys()) == {"a", "b", "c"}

    def test_rejects_unknown_dependency(self):
        with pytest.raises(ValueError, match="unknown"):
            PlanGraph(
                sub_plans={"a": _sp("a")},
                dependencies={"a": {"nonexistent"}},
            )

    def test_rejects_self_dependency(self):
        with pytest.raises(ValueError, match="cannot depend on itself"):
            PlanGraph(
                sub_plans={"a": _sp("a")},
                dependencies={"a": {"a"}},
            )

    def test_rejects_cycle(self):
        with pytest.raises(ValueError, match="cycle"):
            PlanGraph(
                sub_plans={
                    "a": _sp("a"),
                    "b": _sp("b"),
                },
                dependencies={
                    "a": {"b"},
                    "b": {"a"},
                },
            )

    def test_rejects_three_node_cycle(self):
        with pytest.raises(ValueError, match="cycle"):
            PlanGraph(
                sub_plans={
                    "a": _sp("a"),
                    "b": _sp("b"),
                    "c": _sp("c"),
                },
                dependencies={
                    "a": {"c"},
                    "b": {"a"},
                    "c": {"b"},
                },
            )

    def test_diamond_is_valid(self):
        """A → B, A → C, B → D, C → D  (diamond, no cycle)."""
        g = PlanGraph(
            sub_plans={
                "a": _sp("a"),
                "b": _sp("b"),
                "c": _sp("c"),
                "d": _sp("d"),
            },
            dependencies={
                "a": set(),
                "b": {"a"},
                "c": {"a"},
                "d": {"b", "c"},
            },
        )
        assert set(g.sub_plans.keys()) == {"a", "b", "c", "d"}


# ── PlanGraph mutation ──────────────────────────────────────────────


class TestPlanGraphMutation:
    def test_add_sub_plan(self):
        g = _simple_graph()
        g.add_sub_plan(_sp("d"), depends_on={"c"})
        assert "d" in g.sub_plans
        assert g.dependencies["d"] == {"c"}

    def test_add_sub_plan_rejects_cycle(self):
        g = _simple_graph()
        with pytest.raises(ValueError):
            g.add_sub_plan(_sp("d"), depends_on={"c"})
            g.add_dependency("a", "d")  # would create a→b→c→d→a? No, but let's test direct cycle
        # Direct cycle: add d depending on c, then make a depend on d
        g2 = _simple_graph()
        g2.add_sub_plan(_sp("d"), depends_on={"c"})
        with pytest.raises(ValueError):
            g2.add_dependency("a", "d")

    def test_add_duplicate_raises(self):
        g = _simple_graph()
        with pytest.raises(ValueError, match="already exists"):
            g.add_sub_plan(_sp("a"))

    def test_remove_sub_plan(self):
        g = _simple_graph()
        removed = g.remove_sub_plan("b")
        assert removed.scope_id == "b"
        assert "b" not in g.sub_plans
        # c's dependency on b should be cleaned up
        assert "b" not in g.dependencies.get("c", set())

    def test_remove_nonexistent_raises(self):
        g = _simple_graph()
        with pytest.raises(KeyError):
            g.remove_sub_plan("z")

    def test_add_dependency(self):
        g = PlanGraph(
            sub_plans={"a": _sp("a"), "b": _sp("b")},
            dependencies={"a": set(), "b": set()},
        )
        g.add_dependency("b", "a")
        assert "a" in g.dependencies["b"]

    def test_add_dependency_rejects_cycle(self):
        g = _simple_graph()  # a → b → c
        with pytest.raises(ValueError):
            g.add_dependency("a", "c")  # would create cycle: a depends on c, but c depends on b depends on a

    def test_get_returns_sub_plan(self):
        g = _simple_graph()
        assert g.get("a") is not None
        assert g.get("a").scope_id == "a"

    def test_get_returns_none_for_missing(self):
        g = _simple_graph()
        assert g.get("z") is None

    def test_all_leaves_done(self):
        g = _simple_graph()
        # Only leaf is "c"
        c = g.sub_plans["c"]
        c.approve()
        c.mark_executing()
        c.mark_done()
        assert g.all_leaves_done()

    def test_all_leaves_not_done(self):
        g = _simple_graph()
        assert not g.all_leaves_done()
