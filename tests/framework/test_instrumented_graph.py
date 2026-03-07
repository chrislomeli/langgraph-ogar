"""
Tests for InstrumentedGraph and interceptors.

These tests use a trivial state schema and dummy nodes —
no dependency on symbolic_music or intent.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict
from unittest.mock import MagicMock

import pytest

from framework.langgraph_ext.instrumented_graph import InstrumentedGraph, Interceptor, Middleware
from framework.langgraph_ext.interceptors import LoggingInterceptor, MetricsInterceptor


# ── Fixtures ────────────────────────────────────────────────────────

class SimpleState(TypedDict):
    value: int


class SpyInterceptor(Interceptor):
    """Records all calls for assertion."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def before(self, node_name: str, state: Any) -> None:
        self.calls.append((node_name, "before"))

    def after(self, node_name: str, state: Any, result: Any) -> None:
        self.calls.append((node_name, "after"))

    def on_error(self, node_name: str, state: Any, error: Exception) -> None:
        self.calls.append((node_name, "on_error"))


def increment(state: SimpleState) -> dict:
    return {"value": state["value"] + 1}


def exploding_node(state: SimpleState) -> dict:
    raise RuntimeError("boom")


# ── Tests ───────────────────────────────────────────────────────────

class TestInstrumentedGraph:

    def test_interceptor_hooks_fire_in_order(self):
        spy = SpyInterceptor()
        graph = InstrumentedGraph(SimpleState, interceptors=[spy])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 0})

        assert result["value"] == 1
        assert spy.calls == [("inc", "before"), ("inc", "after")]

    def test_on_error_fires_on_exception(self):
        spy = SpyInterceptor()
        graph = InstrumentedGraph(SimpleState, interceptors=[spy])
        graph.add_node("boom", exploding_node)
        graph.set_entry_point("boom")
        graph.set_finish_point("boom")

        app = graph.compile()
        with pytest.raises(RuntimeError, match="boom"):
            app.invoke({"value": 0})

        assert spy.calls == [("boom", "before"), ("boom", "on_error")]

    def test_broken_interceptor_does_not_crash_graph(self):
        """A broken interceptor should be swallowed, not propagated."""

        class BrokenInterceptor(Interceptor):
            def before(self, node_name, state):
                raise ValueError("interceptor bug")

            def after(self, node_name, state, result):
                raise ValueError("interceptor bug")

            def on_error(self, node_name, state, error):
                raise ValueError("interceptor bug")

        graph = InstrumentedGraph(SimpleState, interceptors=[BrokenInterceptor()])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 5})
        assert result["value"] == 6  # node still ran successfully

    def test_multiple_interceptors(self):
        spy1 = SpyInterceptor()
        spy2 = SpyInterceptor()
        graph = InstrumentedGraph(SimpleState, interceptors=[spy1, spy2])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        app.invoke({"value": 0})

        assert spy1.calls == [("inc", "before"), ("inc", "after")]
        assert spy2.calls == [("inc", "before"), ("inc", "after")]

    def test_add_interceptor_after_construction(self):
        spy = SpyInterceptor()
        graph = InstrumentedGraph(SimpleState)
        graph.add_interceptor(spy)
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        app.invoke({"value": 0})

        assert len(spy.calls) == 2

    def test_no_interceptors_works_normally(self):
        graph = InstrumentedGraph(SimpleState)
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 10})
        assert result["value"] == 11


class TestLoggingInterceptor:

    def test_logs_before_and_after(self, caplog):
        ic = LoggingInterceptor(level=logging.INFO)
        graph = InstrumentedGraph(SimpleState, interceptors=[ic])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        with caplog.at_level(logging.INFO):
            app.invoke({"value": 0})

        messages = [r.message for r in caplog.records]
        assert any("entering" in m and "inc" in m for m in messages)
        assert any("completed" in m and "inc" in m for m in messages)


class TestMetricsInterceptor:

    def test_collects_call_count_and_duration(self):
        ic = MetricsInterceptor()
        graph = InstrumentedGraph(SimpleState, interceptors=[ic])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        app.invoke({"value": 0})
        app.invoke({"value": 0})

        snap = ic.snapshot()
        assert snap["inc"]["call_count"] == 2
        assert snap["inc"]["error_count"] == 0
        assert snap["inc"]["total_duration"] > 0

    def test_tracks_errors(self):
        ic = MetricsInterceptor()
        graph = InstrumentedGraph(SimpleState, interceptors=[ic])
        graph.add_node("boom", exploding_node)
        graph.set_entry_point("boom")
        graph.set_finish_point("boom")

        app = graph.compile()
        with pytest.raises(RuntimeError):
            app.invoke({"value": 0})

        snap = ic.snapshot()
        assert snap["boom"]["call_count"] == 1
        assert snap["boom"]["error_count"] == 1


# -- Middleware helpers -----------------------------------------------

class DoubleMiddleware(Middleware):
    """Doubles the 'value' in the result dict."""

    def transform(self, node_name: str, state: Any, result: Any) -> Any:
        if isinstance(result, dict) and "value" in result:
            return {**result, "value": result["value"] * 2}
        return result


class TagMiddleware(Middleware):
    """Adds a '_tagged_by' key to the result."""

    def __init__(self, tag: str):
        self._tag = tag

    def transform(self, node_name: str, state: Any, result: Any) -> Any:
        if isinstance(result, dict):
            return {**result, "_tagged_by": self._tag}
        return result


class BrokenMiddleware(Middleware):
    """Always raises -- used to verify middleware errors propagate."""

    def transform(self, node_name: str, state: Any, result: Any) -> Any:
        raise RuntimeError("middleware bug")


# -- Middleware tests -------------------------------------------------

class TestMiddleware:

    def test_middleware_transforms_result(self):
        graph = InstrumentedGraph(SimpleState, middleware=[DoubleMiddleware()])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 0})
        # increment returns 1, DoubleMiddleware doubles to 2
        assert result["value"] == 2

    def test_middleware_chains_in_order(self):
        # DoubleMiddleware first (1 -> 2), then DoubleMiddleware again (2 -> 4)
        graph = InstrumentedGraph(
            SimpleState,
            middleware=[DoubleMiddleware(), DoubleMiddleware()],
        )
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 0})
        assert result["value"] == 4

    def test_middleware_runs_after_interceptors(self):
        spy = SpyInterceptor()
        graph = InstrumentedGraph(
            SimpleState,
            interceptors=[spy],
            middleware=[DoubleMiddleware()],
        )
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 0})

        # Interceptor saw the original result (before middleware)
        assert spy.calls == [("inc", "before"), ("inc", "after")]
        # Middleware doubled the value
        assert result["value"] == 2

    def test_broken_middleware_propagates(self):
        """Unlike interceptors, middleware errors MUST propagate."""
        graph = InstrumentedGraph(SimpleState, middleware=[BrokenMiddleware()])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        with pytest.raises(RuntimeError, match="middleware bug"):
            app.invoke({"value": 0})

    def test_add_middleware_after_construction(self):
        graph = InstrumentedGraph(SimpleState)
        graph.add_middleware(DoubleMiddleware())
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 0})
        assert result["value"] == 2

    def test_middleware_only_no_interceptors(self):
        graph = InstrumentedGraph(SimpleState, middleware=[DoubleMiddleware()])
        graph.add_node("inc", increment)
        graph.set_entry_point("inc")
        graph.set_finish_point("inc")

        app = graph.compile()
        result = app.invoke({"value": 5})
        # increment: 5 -> 6, double: 6 -> 12
        assert result["value"] == 12
