"""Tests for planning.dag — DAG operations, traversal, and invalidation."""

from __future__ import annotations

import pytest

from framework.langgraph_ext.planning.models import (
    PlanGraph,
    SubPlan,
    SubPlanStatus,
)
from framework.langgraph_ext.planning.dag import (
    CycleError,
    downstream,
    invalidate_downstream,
    leaves,
    parallel_groups,
    ready_to_execute,
    roots,
    topological_sort,
    upstream,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _sp(scope_id: str, scope_type: str = "generic", **kwargs) -> SubPlan:
    return SubPlan(scope_id=scope_id, scope_type=scope_type, **kwargs)


def _linear() -> PlanGraph:
    """A → B → C"""
    return PlanGraph(
        title="linear",
        sub_plans={"a": _sp("a"), "b": _sp("b"), "c": _sp("c")},
        dependencies={"a": set(), "b": {"a"}, "c": {"b"}},
    )


def _diamond() -> PlanGraph:
    """
    A → B → D
    A → C → D
    """
    return PlanGraph(
        title="diamond",
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


def _wide() -> PlanGraph:
    """Three independent roots: X, Y, Z (no edges)."""
    return PlanGraph(
        title="wide",
        sub_plans={"x": _sp("x"), "y": _sp("y"), "z": _sp("z")},
        dependencies={"x": set(), "y": set(), "z": set()},
    )


def _music_like() -> PlanGraph:
    """
    Mimics the music domain plan:
      voices ──────────────────┐
      form ──► harmony ──┐     │
               groove ───┤     │
                         ▼     ▼
                    compilation
                         │
                      rendering
    """
    return PlanGraph(
        title="music",
        sub_plans={
            "voices": _sp("voices", scope_type="voice_plan"),
            "form": _sp("form", scope_type="form_plan"),
            "harmony": _sp("harmony", scope_type="harmony_plan"),
            "groove": _sp("groove", scope_type="groove_plan"),
            "compilation": _sp("compilation", scope_type="compilation"),
            "rendering": _sp("rendering", scope_type="rendering"),
        },
        dependencies={
            "voices": set(),
            "form": set(),
            "harmony": {"form"},
            "groove": {"form"},
            "compilation": {"voices", "harmony", "groove"},
            "rendering": {"compilation"},
        },
    )


# ── Topological sort ────────────────────────────────────────────────


class TestTopologicalSort:
    def test_linear(self):
        order = topological_sort(_linear())
        assert order.index("a") < order.index("b") < order.index("c")

    def test_diamond(self):
        order = topological_sort(_diamond())
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_wide(self):
        order = topological_sort(_wide())
        assert set(order) == {"x", "y", "z"}

    def test_empty(self):
        g = PlanGraph(title="empty")
        assert topological_sort(g) == []

    def test_single_node(self):
        g = PlanGraph(
            sub_plans={"a": _sp("a")},
            dependencies={"a": set()},
        )
        assert topological_sort(g) == ["a"]

    def test_music_like(self):
        order = topological_sort(_music_like())
        # form before harmony and groove
        assert order.index("form") < order.index("harmony")
        assert order.index("form") < order.index("groove")
        # voices, harmony, groove before compilation
        assert order.index("voices") < order.index("compilation")
        assert order.index("harmony") < order.index("compilation")
        assert order.index("groove") < order.index("compilation")
        # compilation before rendering
        assert order.index("compilation") < order.index("rendering")


# ── Roots and leaves ────────────────────────────────────────────────


class TestRootsAndLeaves:
    def test_linear_roots(self):
        assert roots(_linear()) == ["a"]

    def test_linear_leaves(self):
        assert leaves(_linear()) == ["c"]

    def test_diamond_roots(self):
        assert roots(_diamond()) == ["a"]

    def test_diamond_leaves(self):
        assert leaves(_diamond()) == ["d"]

    def test_wide_roots(self):
        assert roots(_wide()) == ["x", "y", "z"]

    def test_wide_leaves(self):
        assert leaves(_wide()) == ["x", "y", "z"]

    def test_music_roots(self):
        assert set(roots(_music_like())) == {"voices", "form"}

    def test_music_leaves(self):
        assert leaves(_music_like()) == ["rendering"]


# ── Downstream / upstream ───────────────────────────────────────────


class TestTraversal:
    def test_downstream_linear(self):
        assert downstream(_linear(), "a") == {"b", "c"}

    def test_downstream_leaf(self):
        assert downstream(_linear(), "c") == set()

    def test_downstream_diamond(self):
        assert downstream(_diamond(), "a") == {"b", "c", "d"}
        assert downstream(_diamond(), "b") == {"d"}

    def test_upstream_linear(self):
        assert upstream(_linear(), "c") == {"a", "b"}

    def test_upstream_root(self):
        assert upstream(_linear(), "a") == set()

    def test_upstream_diamond(self):
        assert upstream(_diamond(), "d") == {"a", "b", "c"}

    def test_music_downstream_form(self):
        ds = downstream(_music_like(), "form")
        assert ds == {"harmony", "groove", "compilation", "rendering"}

    def test_music_upstream_compilation(self):
        us = upstream(_music_like(), "compilation")
        assert us == {"voices", "form", "harmony", "groove"}


# ── Parallel groups ─────────────────────────────────────────────────


class TestParallelGroups:
    def test_linear(self):
        groups = parallel_groups(_linear())
        assert len(groups) == 3
        assert groups[0] == {"a"}
        assert groups[1] == {"b"}
        assert groups[2] == {"c"}

    def test_diamond(self):
        groups = parallel_groups(_diamond())
        assert len(groups) == 3
        assert groups[0] == {"a"}
        assert groups[1] == {"b", "c"}  # parallel
        assert groups[2] == {"d"}

    def test_wide(self):
        groups = parallel_groups(_wide())
        assert len(groups) == 1
        assert groups[0] == {"x", "y", "z"}  # all parallel

    def test_empty(self):
        g = PlanGraph(title="empty")
        assert parallel_groups(g) == []

    def test_music_like(self):
        groups = parallel_groups(_music_like())
        assert groups[0] == {"voices", "form"}  # roots, parallel
        assert groups[1] == {"harmony", "groove"}  # parallel, depend on form
        assert groups[2] == {"compilation"}
        assert groups[3] == {"rendering"}


# ── Ready to execute ────────────────────────────────────────────────


class TestReadyToExecute:
    def test_nothing_ready_initially(self):
        g = _linear()
        assert ready_to_execute(g) == []

    def test_root_ready_after_approve(self):
        g = _linear()
        g.sub_plans["a"].approve()
        assert ready_to_execute(g) == ["a"]

    def test_dependent_not_ready_until_upstream_done(self):
        g = _linear()
        g.sub_plans["a"].approve()
        g.sub_plans["b"].approve()
        # b is approved but a is not done yet
        assert ready_to_execute(g) == ["a"]

    def test_dependent_ready_after_upstream_done(self):
        g = _linear()
        a = g.sub_plans["a"]
        a.approve()
        a.mark_executing()
        a.mark_done()
        g.sub_plans["b"].approve()
        assert ready_to_execute(g) == ["b"]

    def test_diamond_parallel_ready(self):
        g = _diamond()
        a = g.sub_plans["a"]
        a.approve()
        a.mark_executing()
        a.mark_done()
        g.sub_plans["b"].approve()
        g.sub_plans["c"].approve()
        assert ready_to_execute(g) == ["b", "c"]

    def test_locked_counts_as_done_for_deps(self):
        g = _linear()
        a = g.sub_plans["a"]
        a.approve()
        a.lock()
        g.sub_plans["b"].approve()
        assert ready_to_execute(g) == ["b"]


# ── Invalidation ────────────────────────────────────────────────────


class TestInvalidation:
    def _make_all_done(self, g: PlanGraph) -> None:
        """Walk topological order and move every sub-plan to done."""
        order = topological_sort(g)
        for sid in order:
            sp = g.sub_plans[sid]
            sp.approve()
            sp.mark_executing()
            sp.mark_done()

    def test_invalidate_downstream_linear(self):
        g = _linear()
        self._make_all_done(g)
        invalidated = invalidate_downstream(g, "a")
        assert invalidated == {"b", "c"}
        assert g.sub_plans["b"].status == SubPlanStatus.stale
        assert g.sub_plans["c"].status == SubPlanStatus.stale
        assert g.sub_plans["a"].status == SubPlanStatus.done  # unchanged

    def test_invalidate_leaf_affects_nothing(self):
        g = _linear()
        self._make_all_done(g)
        invalidated = invalidate_downstream(g, "c")
        assert invalidated == set()

    def test_invalidate_respects_locked(self):
        g = _linear()
        self._make_all_done(g)
        g.sub_plans["b"].lock()
        invalidated = invalidate_downstream(g, "a")
        # b is locked so it's not invalidated, but c (which depends on b) is
        assert "b" not in invalidated
        assert "c" in invalidated
        assert g.sub_plans["b"].status == SubPlanStatus.locked

    def test_invalidate_music_harmony_change(self):
        g = _music_like()
        self._make_all_done(g)
        invalidated = invalidate_downstream(g, "harmony")
        assert invalidated == {"compilation", "rendering"}
        assert g.sub_plans["groove"].status == SubPlanStatus.done  # unaffected
        assert g.sub_plans["voices"].status == SubPlanStatus.done  # unaffected

    def test_invalidate_music_form_change(self):
        g = _music_like()
        self._make_all_done(g)
        invalidated = invalidate_downstream(g, "form")
        assert invalidated == {"harmony", "groove", "compilation", "rendering"}
