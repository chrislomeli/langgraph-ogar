"""Tests for planning.approval — Approval policies."""

from __future__ import annotations

from framework.langgraph_ext.planning.models import PlanGraph, SubPlan
from framework.langgraph_ext.planning.approval import (
    AlwaysApprove,
    AlwaysReview,
    ReviewStructuralChanges,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _sp(scope_id: str, version: int = 1) -> SubPlan:
    return SubPlan(scope_id=scope_id, scope_type="generic", version=version)


def _graph() -> PlanGraph:
    return PlanGraph(
        sub_plans={"a": _sp("a"), "b": _sp("b")},
        dependencies={"a": set(), "b": {"a"}},
    )


# ── AlwaysApprove ───────────────────────────────────────────────────


class TestAlwaysApprove:
    def test_never_needs_approval(self):
        policy = AlwaysApprove()
        g = _graph()
        assert not policy.needs_approval(g.sub_plans["a"], g)
        assert not policy.needs_approval(g.sub_plans["b"], g)


# ── AlwaysReview ────────────────────────────────────────────────────


class TestAlwaysReview:
    def test_always_needs_approval(self):
        policy = AlwaysReview()
        g = _graph()
        assert policy.needs_approval(g.sub_plans["a"], g)
        assert policy.needs_approval(g.sub_plans["b"], g)

    def test_even_high_version_needs_approval(self):
        policy = AlwaysReview()
        g = PlanGraph(
            sub_plans={"a": _sp("a", version=5)},
            dependencies={"a": set()},
        )
        assert policy.needs_approval(g.sub_plans["a"], g)


# ── ReviewStructuralChanges ─────────────────────────────────────────


class TestReviewStructuralChanges:
    def test_version_1_needs_approval(self):
        policy = ReviewStructuralChanges()
        g = _graph()
        assert policy.needs_approval(g.sub_plans["a"], g)

    def test_version_2_auto_approved(self):
        policy = ReviewStructuralChanges()
        g = PlanGraph(
            sub_plans={"a": _sp("a", version=2)},
            dependencies={"a": set()},
        )
        assert not policy.needs_approval(g.sub_plans["a"], g)

    def test_re_planned_sub_plan_auto_approved(self):
        policy = ReviewStructuralChanges()
        g = _graph()
        sp = g.sub_plans["a"]
        sp.set_content("new content", planned_by="test")
        # After set_content, version is 2
        assert not policy.needs_approval(sp, g)
