"""
Milestone 4: Fan-out / Fan-in.

Tests verify:
  1. mock_planner produces a plan with voices
  2. Fan-out spawns one compile_voice per voice
  3. Each voice produces independent results
  4. Assembler collects all results
  5. Dynamic: changing voice count changes fan-out count

The graph:
  START → mock_planner → fan_out_voices → compile_voice ×N → assembler → END

KEY CONCEPTS:
  - Send() creates N parallel nodes from runtime data
  - Annotated[list, operator.add] reducer accumulates results
  - assembler sees ALL results after parallel nodes finish
"""

from __future__ import annotations


# ── Test 1: Plan has voices ─────────────────────────────────────────

class TestPlanHasVoices:
    """mock_planner should produce a plan with a voices list."""

    def test_plan_has_voices(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        print("back")
        assert "voices" in result["plan"], "plan should have voices"
        assert len(result["plan"]["voices"]) > 0, "plan should have at least one voice"

    def test_default_plan_has_three_voices(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result["plan"]["voices"] == ["Violin", "Piano", "Cello"]


# ── Test 2: Fan-out produces results per voice ──────────────────────

class TestFanOut:
    """Each voice in the plan should produce a compile result."""

    def test_voice_results_count_matches_plan(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        voice_count = len(result["plan"]["voices"])
        assert len(result["voice_results"]) == voice_count, \
            f"Expected {voice_count} voice results, got {len(result['voice_results'])}"

    def test_each_voice_has_result(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        voice_names = {vr["voice"] for vr in result["voice_results"]}
        expected = {"Violin", "Piano", "Cello"}
        assert voice_names == expected, \
            f"Expected results for {expected}, got {voice_names}"

    def test_voice_result_has_expected_fields(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        for vr in result["voice_results"]:
            assert "voice" in vr, "voice result should have voice name"
            assert "measures" in vr, "voice result should have measures"
            assert "notes" in vr, "voice result should have notes"
            assert "tempo" in vr, "voice result should have tempo"

    def test_voice_results_are_independent(self):
        """Each voice should have its own unique notes."""
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        all_notes = [tuple(vr["notes"]) for vr in result["voice_results"]]
        assert len(set(all_notes)) == len(all_notes), \
            "Each voice should produce unique notes"


# ── Test 3: Assembler merges results ────────────────────────────────

class TestAssembler:
    """Assembler should merge all voice results into a single dict."""

    def test_assembled_exists(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result.get("assembled") is not None, "assembler should produce output"

    def test_assembled_has_all_voices(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assembled = result["assembled"]
        assert assembled["total_voices"] == 3
        assert "Violin" in assembled["voices"]
        assert "Piano" in assembled["voices"]
        assert "Cello" in assembled["voices"]

    def test_assembled_total_measures(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assembled = result["assembled"]
        # 3 voices × 4 measures each = 12 total
        assert assembled["total_measures"] == 12


# ── Test 4: Dynamic fan-out ─────────────────────────────────────────

class TestDynamicFanOut:
    """Changing the plan's voice count should change the fan-out count."""

    def test_custom_plan_with_more_voices(self):
        """Inject a plan with 5 voices and verify 5 results."""
        from graph.m4.graph_builder import build_music_graph, fan_out_voices
        from graph.m4.nodes import compile_voice, assembler
        from graph.m4.state import MusicGraphState
        from langgraph.graph import StateGraph, START, END

        # Build a custom graph with a engine that returns 5 voices
        def five_voice_planner(state: MusicGraphState) -> dict:
            return {
                "plan": {
                    "genre": "Jazz",
                    "key": "Bb Major",
                    "tempo": 160,
                    "sections": ["Head", "Solo", "Head"],
                    "voices": ["Trumpet", "Sax", "Piano", "Bass", "Drums"],
                }
            }

        builder = StateGraph(MusicGraphState)
        builder.add_node("mock_planner", five_voice_planner)
        builder.add_node("compile_voice", compile_voice)
        builder.add_node("assembler", assembler)
        builder.add_edge(START, "mock_planner")
        builder.add_conditional_edges("mock_planner", fan_out_voices)
        builder.add_edge("compile_voice", "assembler")
        builder.add_edge("assembler", END)
        app = builder.compile()

        result = app.invoke({"user_message": "Play some jazz"})

        assert len(result["voice_results"]) == 5, \
            f"Expected 5 voice results, got {len(result['voice_results'])}"
        assert result["assembled"]["total_voices"] == 5

    def test_single_voice_plan(self):
        """Edge case: a plan with just one voice."""
        from graph.m4.graph_builder import build_music_graph, fan_out_voices
        from graph.m4.nodes import compile_voice, assembler
        from graph.m4.state import MusicGraphState
        from langgraph.graph import StateGraph, START, END

        def solo_planner(state: MusicGraphState) -> dict:
            return {
                "plan": {
                    "genre": "Solo",
                    "key": "D Minor",
                    "tempo": 80,
                    "sections": ["Prelude"],
                    "voices": ["Cello"],
                }
            }

        builder = StateGraph(MusicGraphState)
        builder.add_node("mock_planner", solo_planner)
        builder.add_node("compile_voice", compile_voice)
        builder.add_node("assembler", assembler)
        builder.add_edge(START, "mock_planner")
        builder.add_conditional_edges("mock_planner", fan_out_voices)
        builder.add_edge("compile_voice", "assembler")
        builder.add_edge("assembler", END)
        app = builder.compile()

        result = app.invoke({"user_message": "Solo cello piece"})

        assert len(result["voice_results"]) == 1
        assert result["assembled"]["total_voices"] == 1
        assert "Cello" in result["assembled"]["voices"]


# ── Test 5: State preservation ──────────────────────────────────────

class TestStatePreserved:
    """Original state fields should survive through fan-out/fan-in."""

    def test_user_message_preserved(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result["user_message"] == "Write me a classical piece"

    def test_plan_preserved_after_assembly(self):
        from graph.m4.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a classical piece"})

        assert result["plan"]["genre"] == "Classical"
        assert result["plan"]["voices"] == ["Violin", "Piano", "Cello"]
