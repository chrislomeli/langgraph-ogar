"""
Milestone 7: Persistence — Save and Load.

Tests verify:
  1. MusicStore ABC and InMemoryStore work correctly
  2. Save/load/list nodes work via the graph
  3. Create → save → load round-trip preserves artifacts
  4. Version management (save twice → two versions)
  5. Checkpointer enables multi-turn workflows (create, then save)
  6. Store injection — same graph, different stores

KEY CONCEPTS:
  - MusicStore ABC enables dependency injection
  - Nodes receive store via closure (factory pattern)
  - Checkpointer enables multi-turn: create in one invoke, save in another
  - InMemoryStore holds full Python objects — no serialization needed
"""

from __future__ import annotations

import pytest


# ── Test 1: InMemoryStore standalone ────────────────────────────────

class TestInMemoryStore:
    """InMemoryStore should work as a standalone key-value store."""

    def test_save_and_load(self):
        from graph.m7.store import InMemoryStore

        store = InMemoryStore()
        record = store.save(
            title="My Tune",
            sketch="fake_sketch",
            plan="fake_plan",
            compile_result="fake_result",
        )

        assert record.title == "My Tune"
        assert record.version == 1

        loaded = store.load("My Tune")
        assert loaded.plan == "fake_plan"

    def test_auto_version_increment(self):
        from graph.m7.store import InMemoryStore

        store = InMemoryStore()
        store.save("My Tune", "s1", "p1", "r1")
        store.save("My Tune", "s2", "p2", "r2")

        latest = store.load("My Tune")
        assert latest.version == 2
        assert latest.plan == "p2"

        v1 = store.load("My Tune", version=1)
        assert v1.version == 1
        assert v1.plan == "p1"

    def test_load_missing_raises(self):
        from graph.m7.store import InMemoryStore

        store = InMemoryStore()
        with pytest.raises(KeyError, match="not found"):
            store.load("Nonexistent")

    def test_list_projects_empty(self):
        from graph.m7.store import InMemoryStore

        store = InMemoryStore()
        assert store.list_projects() == []

    def test_list_projects(self):
        from graph.m7.store import InMemoryStore

        store = InMemoryStore()
        store.save("Tune A", "s", "p", "r")
        store.save("Tune B", "s", "p", "r")
        store.save("Tune A", "s", "p2", "r2")  # v2

        projects = store.list_projects()
        assert len(projects) == 2

        tune_a = next(p for p in projects if p["title"] == "Tune A")
        assert tune_a["versions"] == 2
        assert tune_a["latest_version"] == 2

    def test_exists(self):
        from graph.m7.store import InMemoryStore

        store = InMemoryStore()
        assert not store.exists("My Tune")
        store.save("My Tune", "s", "p", "r")
        assert store.exists("My Tune")


# ── Test 2: Save node via graph ─────────────────────────────────────

class TestSaveProjectNode:
    """Save node should persist artifacts through the graph."""

    def test_save_after_create(self):
        """Multi-turn: create a composition, then save it."""
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)

        # Turn 1: Create
        config = {"configurable": {"thread_id": "test-save-1"}}
        result = app.invoke(
            {"user_message": "Write me a rock tune in A minor"},
            config,
        )
        assert result.get("plan") is not None

        # Turn 2: Save
        result = app.invoke(
            {"user_message": "Save as My Rock Tune"},
            config,
        )
        assert "Saved" in result["response"]
        assert "My Rock Tune" in result["response"]

        # Verify in store
        assert store.exists("My Rock Tune")

    def test_save_nothing_returns_message(self):
        """Save without creating anything first should give feedback."""
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)

        config = {"configurable": {"thread_id": "test-save-empty"}}
        result = app.invoke(
            {"user_message": "Save as My Tune"},
            config,
        )
        assert "Nothing to save" in result["response"]


# ── Test 3: Load node via graph ─────────────────────────────────────

class TestLoadProjectNode:
    """Load node should restore artifacts into state."""

    def test_load_restores_plan(self):
        """Save then load should restore the plan."""
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)

        # Create and save
        config = {"configurable": {"thread_id": "test-load-1"}}
        app.invoke({"user_message": "Create a rock tune in A minor"}, config)
        app.invoke({"user_message": "Save as My Rock Tune"}, config)

        # Load in a new thread (simulates new session)
        config2 = {"configurable": {"thread_id": "test-load-2"}}
        result = app.invoke(
            {"user_message": "Load My Rock Tune"},
            config2,
        )

        assert "Loaded" in result["response"]
        assert result.get("plan") is not None
        assert result.get("compile_result") is not None

    def test_load_missing_returns_message(self):
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)

        config = {"configurable": {"thread_id": "test-load-miss"}}
        result = app.invoke(
            {"user_message": "Load Nonexistent Tune"},
            config,
        )
        assert "not found" in result["response"]


# ── Test 4: List projects via graph ─────────────────────────────────

class TestListProjectsNode:
    """List node should show all saved projects."""

    def test_list_empty(self):
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)

        config = {"configurable": {"thread_id": "test-list-1"}}
        result = app.invoke(
            {"user_message": "List my projects"},
            config,
        )
        assert "No saved projects" in result["response"]

    def test_list_after_saves(self):
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)

        # Create and save two projects
        config = {"configurable": {"thread_id": "test-list-2"}}
        app.invoke({"user_message": "Create a rock tune"}, config)
        app.invoke({"user_message": "Save as Rock Tune"}, config)

        config2 = {"configurable": {"thread_id": "test-list-3"}}
        app.invoke({"user_message": "Compose a jazz piece"}, config2)
        app.invoke({"user_message": "Save as Jazz Piece"}, config2)

        # List
        config3 = {"configurable": {"thread_id": "test-list-4"}}
        result = app.invoke(
            {"user_message": "List my projects"},
            config3,
        )
        assert "2" in result["response"]  # 2 projects


# ── Test 5: Full round-trip ─────────────────────────────────────────

class TestFullRoundTrip:
    """Create → save → load → verify full pipeline artifacts."""

    def test_create_save_load_round_trip(self):
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph
        from intent.plan_models import PlanBundle
        from intent.compiler_interface import CompileResult

        store = InMemoryStore()
        app = build_music_graph(store=store)

        # Create
        config = {"configurable": {"thread_id": "rt-1"}}
        create_result = app.invoke(
            {"user_message": "Write a rock tune in A minor"},
            config,
        )
        original_plan = create_result["plan"]

        # Save
        app.invoke({"user_message": "Save as My Rock Tune"}, config)

        # Load in fresh session
        config2 = {"configurable": {"thread_id": "rt-2"}}
        load_result = app.invoke(
            {"user_message": "Load My Rock Tune"},
            config2,
        )

        # Verify same plan came back
        loaded_plan = load_result["plan"]
        assert isinstance(loaded_plan, PlanBundle)
        assert loaded_plan.title == original_plan.title
        assert loaded_plan.key == original_plan.key
        assert loaded_plan.tempo_bpm == original_plan.tempo_bpm

        # Verify compile result came back
        assert isinstance(load_result["compile_result"], CompileResult)

    def test_save_two_versions_load_specific(self):
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)

        # Create and save v1
        config = {"configurable": {"thread_id": "ver-1"}}
        app.invoke({"user_message": "Create a rock tune"}, config)
        app.invoke({"user_message": "Save as My Tune"}, config)

        # Create different and save v2
        config2 = {"configurable": {"thread_id": "ver-2"}}
        app.invoke({"user_message": "Compose a jazz piece"}, config2)
        app.invoke({"user_message": "Save as My Tune"}, config2)

        # Verify two versions
        assert len(store._projects["My Tune"]) == 2

        # Load latest (v2) — should be jazz
        loaded = store.load("My Tune")
        assert loaded.version == 2

        # Load v1 — should be rock
        loaded_v1 = store.load("My Tune", version=1)
        assert loaded_v1.version == 1


# ── Test 6: Store injection ─────────────────────────────────────────

class TestStoreInjection:
    """Same graph, different stores — verifying DI works."""

    def test_two_stores_independent(self):
        from graph.m7.store import InMemoryStore
        from graph.m7.graph_builder import build_music_graph

        store_a = InMemoryStore()
        store_b = InMemoryStore()

        app_a = build_music_graph(store=store_a)
        app_b = build_music_graph(store=store_b)

        # Save in store A
        config_a = {"configurable": {"thread_id": "di-a"}}
        app_a.invoke({"user_message": "Create a rock tune"}, config_a)
        app_a.invoke({"user_message": "Save as Tune A"}, config_a)

        # Store B doesn't have it
        assert store_a.exists("Tune A")
        assert not store_b.exists("Tune A")

    def test_default_store_is_in_memory(self):
        from graph.m7.graph_builder import build_music_graph

        # No store argument — should default to InMemoryStore
        app = build_music_graph()

        config = {"configurable": {"thread_id": "default-store"}}
        result = app.invoke(
            {"user_message": "Create a rock tune"},
            config,
        )
        assert result.get("plan") is not None
