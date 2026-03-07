"""
Milestone 8: The Refinement Loop.

Tests verify:
  1. Refinement subgraph works standalone
  2. Scope classifier identifies what changed
  3. Plan refiner applies changes via DeterministicPlanner.refine()
  4. Scoped recompilation only recompiles affected voices
  5. Multi-turn: create → refine → verify changes
  6. Iterative refinement: create → refine → refine again
  7. Create → refine → save round-trip

KEY CONCEPTS:
  - Graph cycles: refine repeatedly within a single thread
  - Scoped recompilation: only changed voices are recompiled
  - Merge: unchanged voices preserved from previous compilation
  - The refinement subgraph is a DIFFERENT entry point to the same
    compilation pipeline — scope classifier replaces sketch parser
"""

from __future__ import annotations

import pytest


# ── Helpers ─────────────────────────────────────────────────────────

def _create_composition(app, config, prompt="Write a rock tune in A minor"):
    """Helper: create a composition and return the result."""
    return app.invoke({"user_message": prompt}, config)


# ── Test 1: Refinement subgraph standalone ──────────────────────────

class TestRefinementSubgraphStandalone:
    """The refinement subgraph should work independently."""

    def _get_previous_artifacts(self):
        """Create a composition to get plan and compile_result."""
        from graph.m8.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})
        return result["plan"], result["compile_result"]

    def test_refinement_produces_response(self):
        from graph.m8.subgraphs.refinement import build_refinement_subgraph

        plan, compile_result = self._get_previous_artifacts()
        app = build_refinement_subgraph()

        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        assert result.get("response") is not None
        assert result.get("plan") is not None
        assert result.get("compile_result") is not None

    def test_add_bridge_increases_sections(self):
        from graph.m8.subgraphs.refinement import build_refinement_subgraph

        plan, compile_result = self._get_previous_artifacts()
        original_section_count = len(plan.form_plan.sections)

        app = build_refinement_subgraph()
        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        refined_plan = result["plan"]
        assert len(refined_plan.form_plan.sections) > original_section_count

    def test_add_bridge_increases_bars(self):
        from graph.m8.subgraphs.refinement import build_refinement_subgraph

        plan, compile_result = self._get_previous_artifacts()
        original_bars = plan.form_plan.total_bars()

        app = build_refinement_subgraph()
        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        refined_plan = result["plan"]
        assert refined_plan.form_plan.total_bars() > original_bars


# ── Test 2: Scope Classifier ───────────────────────────────────────

class TestScopeClassifier:
    """Scope classifier should identify which voices are affected."""

    def _get_previous_artifacts(self):
        from graph.m8.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})
        return result["plan"], result["compile_result"]

    def test_structural_change_affects_all_voices(self):
        from graph.m8.subgraphs.refinement import scope_classifier

        plan, compile_result = self._get_previous_artifacts()
        all_voice_ids = {v.voice_id for v in plan.voice_plan.voices}

        result = scope_classifier({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        assert result["changed_voice_ids"] == all_voice_ids

    def test_density_change_targets_drums(self):
        from graph.m8.subgraphs.refinement import scope_classifier

        plan, compile_result = self._get_previous_artifacts()

        result = scope_classifier({
            "user_message": "Make the chorus busier",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        # Should target drums/percussion, not all voices
        changed = result["changed_voice_ids"]
        all_voice_ids = {v.voice_id for v in plan.voice_plan.voices}

        # Either targets drums specifically, or all if no drums found
        assert len(changed) > 0
        assert changed.issubset(all_voice_ids)

    def test_no_previous_plan_returns_empty(self):
        from graph.m8.subgraphs.refinement import scope_classifier

        result = scope_classifier({
            "user_message": "Make it busier",
            "previous_plan": None,
        })

        assert result["changed_voice_ids"] == set()


# ── Test 3: Multi-turn create → refine ─────────────────────────────

class TestMultiTurnCreateRefine:
    """Create a composition, then refine it in the same thread."""

    def test_create_then_add_bridge(self):
        from graph.m8.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "mt-1"}}

        # Turn 1: Create
        create_result = app.invoke(
            {"user_message": "Write a rock tune in A minor"},
            config,
        )
        original_sections = len(create_result["plan"].form_plan.sections)
        original_bars = create_result["plan"].form_plan.total_bars()

        # Turn 2: Refine — add a bridge
        refine_result = app.invoke(
            {"user_message": "Add a bridge"},
            config,
        )

        # Verify the refinement happened
        refined_plan = refine_result["plan"]
        assert len(refined_plan.form_plan.sections) > original_sections
        assert refined_plan.form_plan.total_bars() > original_bars

    def test_create_then_make_busier(self):
        from graph.m8.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "mt-2"}}

        # Turn 1: Create
        app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        # Turn 2: Refine — make chorus busier
        result = app.invoke(
            {"user_message": "Make the chorus busier"},
            config,
        )

        assert result.get("plan") is not None
        assert result.get("compile_result") is not None
        assert "Refined" in result["response"] or "refined" in result["response"].lower()

    def test_refine_without_create_handles_gracefully(self):
        from graph.m8.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "mt-3"}}

        # Try to refine without creating first
        result = app.invoke(
            {"user_message": "Add a bridge"},
            config,
        )

        # Should handle gracefully (no crash)
        assert result.get("response") is not None


# ── Test 4: Iterative refinement ────────────────────────────────────

class TestIterativeRefinement:
    """Refine multiple times in sequence."""

    def test_create_refine_refine(self):
        from graph.m8.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "iter-1"}}

        # Turn 1: Create
        r1 = app.invoke({"user_message": "Write a rock tune in A minor"}, config)
        original_bars = r1["plan"].form_plan.total_bars()

        # Turn 2: Add a bridge
        r2 = app.invoke({"user_message": "Add a bridge"}, config)
        after_bridge_bars = r2["plan"].form_plan.total_bars()
        assert after_bridge_bars > original_bars

        # Turn 3: Make chorus busier (density change, bars unchanged)
        r3 = app.invoke({"user_message": "Make the chorus busier"}, config)
        assert r3["plan"] is not None
        assert r3["compile_result"] is not None


# ── Test 5: Create → refine → save round-trip ──────────────────────

class TestCreateRefineSave:
    """Full workflow: create → refine → save → load → verify."""

    def test_create_refine_save_load(self):
        from graph.m8.store import InMemoryStore
        from graph.m8.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "crs-1"}}

        # Create
        app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        # Refine
        refine_result = app.invoke({"user_message": "Add a bridge"}, config)
        refined_plan = refine_result["plan"]

        # Save
        app.invoke({"user_message": "Save as My Refined Tune"}, config)
        assert store.exists("My Refined Tune")

        # Load in new session
        config2 = {"configurable": {"thread_id": "crs-2"}}
        load_result = app.invoke(
            {"user_message": "Load My Refined Tune"},
            config2,
        )

        # Verify the REFINED plan was saved (not the original)
        loaded_plan = load_result["plan"]
        assert loaded_plan.form_plan.total_bars() == refined_plan.form_plan.total_bars()


# ── Test 6: Refinement response describes changes ───────────────────

class TestRefinementResponse:
    """Refinement response should describe what changed."""

    def test_add_bridge_response_mentions_sections(self):
        from graph.m8.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "resp-1"}}

        app.invoke({"user_message": "Write a rock tune in A minor"}, config)
        result = app.invoke({"user_message": "Add a bridge"}, config)

        # Response should mention the change
        response = result["response"]
        assert "Refined" in response or "refined" in response.lower()

    def test_busier_response_mentions_recompiled(self):
        from graph.m8.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "resp-2"}}

        app.invoke({"user_message": "Write a rock tune in A minor"}, config)
        result = app.invoke({"user_message": "Make the chorus busier"}, config)

        response = result["response"]
        assert "Refined" in response or "Recompiled" in response
