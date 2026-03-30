"""
Milestone 10: InstrumentedGraph -- Observability.

Tests verify:
  1. MetricsInterceptor tracks timing and call counts
  2. LoggingInterceptor captures node events
  3. Creation subgraph produces identical results with instrumentation
  4. Refinement subgraph works with instrumentation
  5. Full parent graph works with observability
  6. Metrics are collected across subgraph nodes

KEY CONCEPTS:
  - InstrumentedGraph: drop-in replacement for StateGraph
  - Interceptors: observe-only (logging, metrics) -- errors swallowed
  - Execution order: before hooks -> node -> after hooks
  - Nodes still use M9 pattern (registry handler direct calls)
"""

from __future__ import annotations

import logging
import pytest


# -- Test 1: MetricsInterceptor -----------------------------------

class TestMetricsInterceptor:
    """MetricsInterceptor should track call counts and durations."""

    def test_metrics_collected_in_creation_subgraph(self):
        from graph.m10.tool_defs import build_tool_registry
        from graph.m10.subgraphs.creation import build_creation_subgraph
        from framework.langgraph_ext.tool_client.client import LocalToolClient
        from framework.langgraph_ext.interceptors.metrics_interceptor import MetricsInterceptor

        registry = build_tool_registry(store=None)
        client = LocalToolClient(registry)
        metrics = MetricsInterceptor()

        app = build_creation_subgraph(client, metrics_interceptor=metrics)
        app.invoke({"user_message": "Rock tune in A minor"})

        snapshot = metrics.snapshot()
        assert "sketch_parser" in snapshot
        assert "engine" in snapshot
        assert "compiler" in snapshot
        assert "presenter" in snapshot

        # Each node called exactly once
        for name in ["sketch_parser", "engine", "compiler", "presenter"]:
            assert snapshot[name]["call_count"] == 1
            assert snapshot[name]["error_count"] == 0
            assert snapshot[name]["last_duration"] > 0

    def test_metrics_avg_duration(self):
        from graph.m10.tool_defs import build_tool_registry
        from graph.m10.subgraphs.creation import build_creation_subgraph
        from framework.langgraph_ext.tool_client.client import LocalToolClient
        from framework.langgraph_ext.interceptors.metrics_interceptor import MetricsInterceptor

        registry = build_tool_registry(store=None)
        client = LocalToolClient(registry)
        metrics = MetricsInterceptor()

        app = build_creation_subgraph(client, metrics_interceptor=metrics)

        # Invoke twice
        app.invoke({"user_message": "Rock tune in A minor"})
        app.invoke({"user_message": "Jazz ballad in C major"})

        snapshot = metrics.snapshot()
        assert snapshot["engine"]["call_count"] == 2
        assert snapshot["engine"]["avg_duration"] > 0


# -- Test 2: LoggingInterceptor -----------------------------------

class TestLoggingInterceptor:
    """LoggingInterceptor should log node events."""

    def test_logging_interceptor_captures_events(self, caplog):
        from graph.m10.tool_defs import build_tool_registry
        from graph.m10.subgraphs.creation import build_creation_subgraph
        from framework.langgraph_ext.tool_client.client import LocalToolClient
        from framework.langgraph_ext.interceptors.logging_interceptor import LoggingInterceptor

        registry = build_tool_registry(store=None)
        client = LocalToolClient(registry)
        log_interceptor = LoggingInterceptor(level=logging.INFO)

        app = build_creation_subgraph(client, logging_interceptor=log_interceptor)

        with caplog.at_level(logging.INFO):
            app.invoke({"user_message": "Rock tune in A minor"})

        # Should see enter/exit messages for each node
        log_text = caplog.text
        assert "entering" in log_text.lower() or "\u25b6" in log_text
        assert "completed" in log_text.lower() or "\u2713" in log_text


# -- Test 3: Creation subgraph with instrumentation ----------------

class TestCreationSubgraphInstrumented:
    """Creation subgraph should produce correct results with InstrumentedGraph."""

    def _build_creation_app(self):
        from graph.m10.tool_defs import build_tool_registry
        from graph.m10.subgraphs.creation import build_creation_subgraph
        from framework.langgraph_ext.tool_client.client import LocalToolClient

        registry = build_tool_registry(store=None)
        client = LocalToolClient(registry)
        return build_creation_subgraph(client)

    def test_creation_produces_plan(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "plan" in result
        assert result["plan"] is not None
        assert hasattr(result["plan"], "title")

    def test_creation_produces_compile_result(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "compile_result" in result
        assert hasattr(result["compile_result"], "composition")

    def test_creation_produces_response(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "response" in result
        assert "Created" in result["response"]


# -- Test 4: Refinement subgraph with instrumentation --------------

class TestRefinementSubgraphInstrumented:
    """Refinement subgraph should work with InstrumentedGraph."""

    def _get_previous_artifacts(self):
        from graph.m10.tool_defs import build_tool_registry
        from graph.m10.subgraphs.creation import build_creation_subgraph
        from framework.langgraph_ext.tool_client.client import LocalToolClient

        registry = build_tool_registry(store=None)
        client = LocalToolClient(registry)
        app = build_creation_subgraph(client)
        result = app.invoke({"user_message": "Rock tune in A minor"})
        return result["plan"], result["compile_result"]

    def _build_refinement_app(self):
        from graph.m10.tool_defs import build_tool_registry
        from graph.m10.subgraphs.refinement import build_refinement_subgraph
        from framework.langgraph_ext.tool_client.client import LocalToolClient

        registry = build_tool_registry(store=None)
        client = LocalToolClient(registry)
        return build_refinement_subgraph(client)

    def test_add_bridge_refinement(self):
        plan, compile_result = self._get_previous_artifacts()
        app = self._build_refinement_app()

        old_sections = len(plan.form_plan.sections)
        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        assert "plan" in result
        new_sections = len(result["plan"].form_plan.sections)
        assert new_sections > old_sections


# -- Test 5: Full parent graph with observability ------------------

class TestFullGraphInstrumented:
    """The parent graph should work end-to-end with instrumented subgraphs."""

    def test_create_composition_with_metrics(self):
        from graph.m10.graph_builder import build_music_graph

        app, metrics = build_music_graph()
        config = {"configurable": {"thread_id": "m10-1"}}
        result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        assert "response" in result
        assert "Created" in result["response"]

        # Subgraph nodes should have metrics
        snapshot = metrics.snapshot()
        assert "sketch_parser" in snapshot
        assert snapshot["sketch_parser"]["call_count"] == 1

    def test_create_then_refine_with_metrics(self):
        from graph.m10.graph_builder import build_music_graph

        app, metrics = build_music_graph()
        config = {"configurable": {"thread_id": "m10-2"}}

        # Create
        create_result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)
        old_bars = create_result["plan"].form_plan.total_bars()

        # Refine
        refine_result = app.invoke({"user_message": "Add a bridge"}, config)
        new_bars = refine_result["plan"].form_plan.total_bars()

        assert new_bars > old_bars

        # Subgraph engine called twice (once for create, once for refine via plan_refiner)
        snapshot = metrics.snapshot()
        assert "engine" in snapshot

    def test_create_save_load_with_metrics(self):
        from graph.m10.store import InMemoryStore
        from graph.m10.graph_builder import build_music_graph

        store = InMemoryStore()
        app, metrics = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m10-3"}}

        # Create
        app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        # Save
        app.invoke({"user_message": "Save as My M10 Tune"}, config)
        assert store.exists("My M10 Tune")

        # Load in new session
        config2 = {"configurable": {"thread_id": "m10-4"}}
        load_result = app.invoke({"user_message": "Load My M10 Tune"}, config2)

        assert load_result["plan"] is not None
        assert hasattr(load_result["plan"], "title")

    def test_list_projects_with_metrics(self):
        from graph.m10.store import InMemoryStore
        from graph.m10.graph_builder import build_music_graph

        store = InMemoryStore()
        app, metrics = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m10-5"}}

        result = app.invoke({"user_message": "List my projects"}, config)
        assert "No saved projects" in result["response"]
