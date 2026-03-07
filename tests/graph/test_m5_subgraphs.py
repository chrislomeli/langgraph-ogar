"""
Milestone 5: Subgraphs.

Tests verify:
  1. Creation subgraph works independently (standalone)
  2. Parent graph routes to creation subgraph for "new" intents
  3. Parent graph routes to answerer for non-creation intents
  4. State flows correctly between parent and child (overlapping fields)
  5. Subgraph internal pipeline runs completely

The parent graph:
  START → intent_router → conditional → creation subgraph → END
                                      → answerer → END

The creation subgraph (internal):
  START → mock_planner → fan_out_voices → compile_voice ×N → assembler → presenter → END

KEY CONCEPTS:
  - A compiled subgraph is used as a node in the parent graph
  - State mapping happens via overlapping field names
  - Subgraphs are independently testable
"""

from __future__ import annotations


# ── Test 1: Subgraph standalone ─────────────────────────────────────

class TestSubgraphStandalone:
    """The creation subgraph should work independently, without the parent."""

    def test_subgraph_produces_response(self):
        from graph.m5.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        print("Done")

        assert result.get("response") is not None, "subgraph should produce a response"

    def test_subgraph_has_plan(self):
        from graph.m5.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result["plan"]["genre"] == "Classical"
        assert result["plan"]["voices"] == ["Violin", "Piano", "Cello"]

    def test_subgraph_has_assembled(self):
        from graph.m5.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result["assembled"]["total_voices"] == 3
        assert "Violin" in result["assembled"]["voices"]

    def test_subgraph_fan_out_works(self):
        from graph.m5.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert len(result["voice_results"]) == 3
        voice_names = {vr["voice"] for vr in result["voice_results"]}
        assert voice_names == {"Violin", "Piano", "Cello"}

    def test_subgraph_jazz_plan(self):
        from graph.m5.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Write me a jazz tune"})

        assert result["plan"]["genre"] == "Jazz"
        assert len(result["voice_results"]) == 4
        assert result["assembled"]["total_voices"] == 4

    def test_subgraph_response_contains_genre(self):
        from graph.m5.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert "Classical" in result["response"]
        assert "C Major" in result["response"]


# ── Test 2: Parent routes to creation subgraph ──────────────────────

class TestParentRoutesToCreation:
    """Parent graph should route creation intents to the creation subgraph."""

    def test_creation_intent_produces_response(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result.get("response") is not None
        assert "Classical" in result["response"]

    def test_creation_intent_has_plan(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Create a jazz tune"})

        assert result["plan"]["genre"] == "Jazz"

    def test_creation_intent_has_assembled(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Compose a classical piece"})

        assert result["assembled"]["total_voices"] == 3

    def test_creation_intent_has_voice_results(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a jazz tune"})

        assert len(result["voice_results"]) == 4


# ── Test 3: Parent routes non-creation to answerer ──────────────────

class TestParentRoutesToAnswerer:
    """Non-creation intents should route to the answerer node."""

    def test_question_routes_to_answerer(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "What key is the bridge in?"})

        assert "[Answerer]" in result["response"]

    def test_refine_routes_to_answerer(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Make the chorus louder"})

        assert "[Answerer]" in result["response"]

    def test_answerer_does_not_produce_plan(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "What key is the bridge in?"})

        assert result.get("plan") is None
        assert result.get("assembled") is None


# ── Test 4: State flows between parent and child ────────────────────

class TestStateMappingParentChild:
    """State should flow correctly between parent and subgraph via
    overlapping field names."""

    def test_user_message_reaches_subgraph(self):
        """user_message is in both ParentState and CreationState,
        so it should be passed into the subgraph."""
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a jazz tune"})

        # Jazz plan proves user_message reached the subgraph
        assert result["plan"]["genre"] == "Jazz"

    def test_subgraph_output_returns_to_parent(self):
        """Fields set by the subgraph should be visible in parent state."""
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        # All these fields were set INSIDE the subgraph
        assert result.get("plan") is not None
        assert result.get("voice_results") is not None
        assert result.get("assembled") is not None
        assert result.get("response") is not None

    def test_intent_type_set_by_parent(self):
        """intent_type is set by the parent router, not the subgraph."""
        from graph.m5.graph_builder import build_music_graph
        from graph.m5.state import IntentType

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result["intent_type"] == IntentType.NEW_SKETCH


# ── Test 5: Full pipeline through parent ────────────────────────────

class TestFullPipeline:
    """End-to-end: parent → subgraph → all internal nodes → back to parent."""

    def test_classical_full_pipeline(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        print("test_classical_full_pipeline complete")

        # Verify every stage ran
        assert result["plan"]["genre"] == "Classical"
        assert len(result["voice_results"]) == 3
        assert result["assembled"]["total_voices"] == 3
        assert "Classical" in result["response"]
        assert "C Major" in result["response"]

    def test_jazz_full_pipeline(self):
        from graph.m5.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Create a jazz tune"})

        assert result["plan"]["genre"] == "Jazz"
        assert len(result["voice_results"]) == 4
        assert result["assembled"]["total_voices"] == 4
        assert "Jazz" in result["response"]
        assert "Bb Major" in result["response"]
