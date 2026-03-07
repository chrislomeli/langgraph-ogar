"""
Milestone 6: Wire in the Real Tools.

Tests verify:
  1. Sketch parser creates a valid Sketch from user message
  2. DeterministicPlanner produces a real PlanBundle
  3. PatternCompiler produces a real CompileResult
  4. render_composition produces a music21 Score
  5. Full pipeline: user message → plan → compile → render → summary
  6. Parent graph routing still works with real tools

The creation subgraph:
  START → sketch_parser → engine → compiler → renderer → presenter → END

KEY CONCEPT: The graph structure is identical to M5.
Only the node implementations changed — stubs replaced with real tools.
"""

from __future__ import annotations


# ── Test 1: Sketch Parser ───────────────────────────────────────────

class TestSketchParser:
    """sketch_parser should create a Sketch from user_message."""

    def test_sketch_created(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert result.get("sketch") is not None, "sketch should be created"

    def test_sketch_has_prompt(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert result["sketch"].prompt == "Rock tune in A minor"


# ── Test 2: DeterministicPlanner ────────────────────────────────────

class TestPlanner:
    """DeterministicPlanner should produce a real PlanBundle."""

    def test_plan_is_plan_bundle(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph
        from intent.plan_models import PlanBundle

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert isinstance(result["plan"], PlanBundle)

    def test_plan_has_voices(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        plan = result["plan"]
        assert len(plan.voice_plan.voices) > 0, "plan should have voices"

    def test_plan_has_form(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        plan = result["plan"]
        assert len(plan.form_plan.sections) > 0, "plan should have sections"
        assert plan.form_plan.total_bars() > 0, "plan should have bars"

    def test_plan_detects_key(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        plan = result["plan"]
        assert "A" in plan.key, f"Expected key containing 'A', got '{plan.key}'"
        assert "minor" in plan.key.lower(), f"Expected minor key, got '{plan.key}'"

    def test_plan_detects_genre_from_prompt(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Jazz ballad, slow and moody"})

        plan = result["plan"]
        assert plan.title is not None
        assert plan.tempo_bpm > 0


# ── Test 3: PatternCompiler ─────────────────────────────────────────

class TestCompiler:
    """PatternCompiler should produce a real CompileResult."""

    def test_compile_result_exists(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph
        from intent.compiler_interface import CompileResult

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert isinstance(result["compile_result"], CompileResult)

    def test_compile_result_has_tracks(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        comp = result["compile_result"].composition
        assert len(comp.tracks) > 0, "should have tracks"

    def test_compile_result_has_sections(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        sections = result["compile_result"].sections
        assert len(sections) > 0, "should have generated sections"

    def test_tracks_match_voices(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        plan = result["plan"]
        comp = result["compile_result"].composition
        voice_count = len(plan.voice_plan.voices)
        track_count = len(comp.tracks)
        assert track_count == voice_count, \
            f"Expected {voice_count} tracks, got {track_count}"


# ── Test 4: Renderer ────────────────────────────────────────────────

class TestRenderer:
    """render_composition should produce a music21 Score."""

    def test_score_exists(self):
        import music21 as m21
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert isinstance(result["score"], m21.stream.Score)

    def test_score_has_parts(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        score = result["score"]
        assert len(score.parts) > 0, "score should have parts"

    def test_score_parts_have_measures(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        score = result["score"]
        for part in score.parts:
            measures = part.getElementsByClass("Measure")
            assert len(measures) > 0, f"Part '{part.partName}' should have measures"

    def test_score_parts_have_notes(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        score = result["score"]
        total_notes = sum(len(p.flatten().notes) for p in score.parts)
        assert total_notes > 0, "score should have notes"


# ── Test 5: Full Pipeline (subgraph standalone) ─────────────────────

class TestFullPipelineStandalone:
    """End-to-end creation subgraph with real tools."""

    def test_rock_tune_full_pipeline(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        print("done ")

        # Every stage produced output
        assert result.get("sketch") is not None
        assert result.get("plan") is not None
        assert result.get("compile_result") is not None
        assert result.get("score") is not None
        assert result.get("response") is not None

    def test_response_contains_plan_details(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        response = result["response"]
        assert "A" in response, "response should mention key"
        assert "BPM" in response, "response should mention tempo"

    def test_jazz_prompt(self):
        from graph.m6.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Jazz ballad, piano trio, Bb major"})

        assert result.get("score") is not None
        assert len(result["score"].parts) > 0


# ── Test 6: Parent graph routing ────────────────────────────────────

class TestParentGraphRouting:
    """Parent graph should route to creation subgraph and answerer."""

    def test_creation_intent_produces_score(self):
        from graph.m6.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a rock tune in A minor"})

        print("done ")

        assert result.get("score") is not None
        assert result.get("response") is not None

    def test_question_routes_to_answerer(self):
        from graph.m6.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "What key is this in?"})

        assert "[Answerer]" in result["response"]
        assert result.get("score") is None

    def test_creation_state_flows_to_parent(self):
        from graph.m6.graph_builder import build_music_graph
        from graph.m6.state import IntentType

        app = build_music_graph()
        result = app.invoke({"user_message": "Compose a classical piece"})

        assert result["intent_type"] == IntentType.NEW_SKETCH
        assert result.get("plan") is not None
        assert result.get("compile_result") is not None
        assert result.get("score") is not None
