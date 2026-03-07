"""
Milestone 9: ToolSpec + Registry — Wire the Tool Library.

Tests verify:
  1. ToolSpec definitions have valid Pydantic models
  2. ToolRegistry catalogs all tools with JSON Schema export
  3. LocalToolClient wraps results in ToolResultEnvelope
  4. Tool handlers produce correct domain output
  5. Graph nodes produce identical results via tool client
  6. Multi-turn create → refine → save works through tool client
  7. Provenance metadata is present on every tool call

KEY CONCEPTS:
  - ToolSpec: frozen contract with Pydantic in/out models + handler
  - ToolRegistry: central catalog, JSON Schema export
  - LocalToolClient: validates inputs/outputs, wraps in ToolResultEnvelope
  - Same deterministic logic as M8 — just routed through tool contracts
"""

from __future__ import annotations

import pytest


# ── Test 1: Tool definitions ─────────────────────────────────────

class TestToolDefinitions:
    """ToolSpec contracts should be well-formed."""

    def test_build_registry_without_store(self):
        from graph.m9.tool_defs import build_tool_registry

        registry = build_tool_registry(store=None)
        tools = registry.list_tools()
        assert "parse_sketch" in tools
        assert "plan_composition" in tools
        assert "compile_composition" in tools
        assert "refine_plan" in tools
        # Persistence tools NOT registered without store
        assert "save_project" not in tools
        assert "load_project" not in tools
        assert "list_projects" not in tools

    def test_build_registry_with_store(self):
        from graph.m9.tool_defs import build_tool_registry
        from graph.m9.store import InMemoryStore

        store = InMemoryStore()
        registry = build_tool_registry(store=store)
        tools = registry.list_tools()
        assert len(tools) == 7
        assert "save_project" in tools
        assert "load_project" in tools
        assert "list_projects" in tools

    def test_catalog_has_json_schemas(self):
        from graph.m9.tool_defs import build_tool_registry

        registry = build_tool_registry(store=None)
        catalog = registry.catalog()
        assert len(catalog) == 4

        for entry in catalog:
            assert "name" in entry
            assert "description" in entry
            assert "inputSchema" in entry
            assert "outputSchema" in entry
            assert isinstance(entry["inputSchema"], dict)
            assert isinstance(entry["outputSchema"], dict)

    def test_parse_sketch_spec_has_correct_models(self):
        from graph.m9.tool_defs import build_tool_registry, ParseSketchInput, ParseSketchOutput

        registry = build_tool_registry(store=None)
        spec = registry.get("parse_sketch")
        assert spec.input_model is ParseSketchInput
        assert spec.output_model is ParseSketchOutput
        assert spec.description != ""


# ── Test 2: LocalToolClient + ToolResultEnvelope ─────────────────

class TestLocalToolClient:
    """LocalToolClient should validate and wrap results."""

    def _build_client(self, with_store=False):
        from graph.m9.tool_defs import build_tool_registry
        from graph.m9.store import InMemoryStore
        from framework.langgraph_ext.tool_client.client import LocalToolClient

        store = InMemoryStore() if with_store else None
        registry = build_tool_registry(store=store)
        return LocalToolClient(registry), store

    def test_parse_sketch_returns_envelope(self):
        client, _ = self._build_client()
        envelope = client.call("parse_sketch", {"user_message": "Rock tune in A minor"})

        assert not envelope.is_error
        assert envelope.meta.tool_name == "parse_sketch"
        assert envelope.meta.success is True
        assert envelope.meta.duration_ms >= 0
        assert envelope.meta.input_hash != ""
        assert envelope.structured is not None
        assert "sketch" in envelope.structured

    def test_plan_composition_returns_envelope(self):
        from intent.sketch_models import Sketch

        client, _ = self._build_client()
        sketch = Sketch(prompt="Rock tune in A minor")
        envelope = client.call("plan_composition", {"sketch": sketch})

        assert not envelope.is_error
        assert envelope.meta.tool_name == "plan_composition"
        assert "plan" in envelope.structured

    def test_compile_composition_returns_envelope(self):
        from intent.sketch_models import Sketch
        from intent.planner import DeterministicPlanner

        client, _ = self._build_client()
        sketch = Sketch(prompt="Rock tune in A minor")
        plan = DeterministicPlanner().plan(sketch)

        envelope = client.call("compile_composition", {"plan": plan})

        assert not envelope.is_error
        assert envelope.meta.tool_name == "compile_composition"
        assert "compile_result" in envelope.structured

    def test_refine_plan_returns_envelope(self):
        from intent.sketch_models import Sketch
        from intent.planner import DeterministicPlanner

        client, _ = self._build_client()
        sketch = Sketch(prompt="Rock tune in A minor")
        plan = DeterministicPlanner().plan(sketch)

        envelope = client.call("refine_plan", {
            "plan": plan,
            "prompt": "Add a bridge",
        })

        assert not envelope.is_error
        assert envelope.meta.tool_name == "refine_plan"
        assert "plan" in envelope.structured

    def test_save_and_load_project(self):
        from intent.sketch_models import Sketch
        from intent.planner import DeterministicPlanner
        from intent.compiler import PatternCompiler

        client, store = self._build_client(with_store=True)
        sketch = Sketch(prompt="Rock tune in A minor")
        plan = DeterministicPlanner().plan(sketch)
        result = PatternCompiler().compile(plan)

        # Save
        save_env = client.call("save_project", {
            "title": "My Song",
            "sketch": sketch,
            "plan": plan,
            "compile_result": result,
        })
        assert not save_env.is_error
        assert save_env.payload["title"] == "My Song"
        assert save_env.payload["version"] == 1

        # Load
        load_env = client.call("load_project", {"title": "My Song"})
        assert not load_env.is_error
        assert load_env.payload["title"] == "My Song"
        assert load_env.payload["plan"] is not None

    def test_list_projects(self):
        client, store = self._build_client(with_store=True)

        # Empty list
        env = client.call("list_projects", {})
        assert not env.is_error
        assert env.payload["projects"] == []

    def test_unknown_tool_raises_key_error(self):
        client, _ = self._build_client()
        with pytest.raises(KeyError, match="not_a_tool"):
            client.call("not_a_tool", {})

    def test_envelope_has_content_blocks(self):
        client, _ = self._build_client()
        envelope = client.call("parse_sketch", {"user_message": "Jazz ballad"})

        assert len(envelope.content) > 0
        assert envelope.content[0].type == "text"
        assert len(envelope.content[0].text) > 0

    def test_envelope_model_dump_flat(self):
        client, _ = self._build_client()
        envelope = client.call("parse_sketch", {"user_message": "Jazz ballad"})

        flat = envelope.model_dump_flat()
        assert "_meta" in flat
        assert flat["_meta"]["tool_name"] == "parse_sketch"
        assert "sketch" in flat


# ── Test 3: Creation subgraph via tool client ────────────────────

class TestCreationSubgraphViaToolClient:
    """Creation subgraph should produce identical results via tool client."""

    def _build_creation_app(self):
        from graph.m9.tool_defs import build_tool_registry
        from graph.m9.subgraphs.creation import build_creation_subgraph
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
        assert result["compile_result"] is not None
        assert hasattr(result["compile_result"], "composition")

    def test_creation_produces_response(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "response" in result
        assert "Created" in result["response"]
        assert "BPM" in result["response"]

    def test_rock_tune_has_expected_voices(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Write a rock tune in A minor"})

        plan = result["plan"]
        voice_names = [v.name for v in plan.voice_plan.voices]
        assert len(voice_names) >= 2  # At least drums + bass


# ── Test 4: Refinement subgraph via tool client ──────────────────

class TestRefinementSubgraphViaToolClient:
    """Refinement subgraph should work via tool client."""

    def _get_previous_artifacts(self):
        from graph.m9.tool_defs import build_tool_registry
        from graph.m9.subgraphs.creation import build_creation_subgraph
        from framework.langgraph_ext.tool_client.client import LocalToolClient

        registry = build_tool_registry(store=None)
        client = LocalToolClient(registry)
        app = build_creation_subgraph(client)
        result = app.invoke({"user_message": "Rock tune in A minor"})
        return result["plan"], result["compile_result"]

    def _build_refinement_app(self):
        from graph.m9.tool_defs import build_tool_registry
        from graph.m9.subgraphs.refinement import build_refinement_subgraph
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

    def test_refinement_produces_response(self):
        plan, compile_result = self._get_previous_artifacts()
        app = self._build_refinement_app()

        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        assert "response" in result
        assert "Refined" in result["response"]


# ── Test 5: Full parent graph via tool client ────────────────────

class TestFullGraphViaToolClient:
    """The parent graph should work end-to-end via tool client."""

    def test_create_composition(self):
        from graph.m9.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "m9-1"}}
        result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        assert "response" in result
        assert "Created" in result["response"]

    def test_create_then_refine(self):
        from graph.m9.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "m9-2"}}

        # Create
        create_result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)
        old_bars = create_result["plan"].form_plan.total_bars()

        # Refine
        refine_result = app.invoke({"user_message": "Add a bridge"}, config)
        new_bars = refine_result["plan"].form_plan.total_bars()

        assert new_bars > old_bars
        assert "Refined" in refine_result["response"]

    def test_create_refine_save_load(self):
        from graph.m9.store import InMemoryStore
        from graph.m9.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m9-3"}}

        # Create
        app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        # Refine
        refine_result = app.invoke({"user_message": "Add a bridge"}, config)
        refined_plan = refine_result["plan"]

        # Save
        app.invoke({"user_message": "Save as My M9 Tune"}, config)
        assert store.exists("My M9 Tune")

        # Load in new session
        config2 = {"configurable": {"thread_id": "m9-4"}}
        load_result = app.invoke({"user_message": "Load My M9 Tune"}, config2)

        loaded_plan = load_result["plan"]
        assert loaded_plan.form_plan.total_bars() == refined_plan.form_plan.total_bars()

    def test_list_projects(self):
        from graph.m9.store import InMemoryStore
        from graph.m9.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m9-5"}}

        # Empty list
        result = app.invoke({"user_message": "List my projects"}, config)
        assert "No saved projects" in result["response"]
