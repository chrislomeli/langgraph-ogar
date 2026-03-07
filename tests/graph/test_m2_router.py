"""
Milestone 2: The Router.

Tests verify:
  1. Intent router classifies messages correctly
  2. Routing function returns the right node name
  3. Graph routes different messages to different paths
  4. Graph has the expected conditional edges

YOUR JOB:
  - Implement src/graph/nodes/intent_router.py
  - Update src/graph/graph_builder.py to add router and conditional edges
  - Make these tests pass: pytest tests/graph/test_m2_router.py -v
"""

from __future__ import annotations

from graph.m2.state import IntentType


# ── Test 1: Intent router node ───────────────────────────────────────


class TestIntentRouter:
    """The intent router classifies user messages."""

    def test_classifies_creation_requests(self):
        from graph import intent_router

        messages = [
            "Write me a rock tune",
            "Create a jazz ballad",
            "Make a new pop song",
            "write me something",
        ]
        for msg in messages:
            result = intent_router({"user_message": msg})
            assert result["intent_type"] == IntentType.NEW_SKETCH

    def test_classifies_refinement_requests(self):
        from graph import intent_router

        messages = [
            "Make the chorus busier",
            "Change the bridge to minor",
            "Adjust the tempo",
            "make the drums louder",
        ]
        for msg in messages:
            result = intent_router({"user_message": msg})
            assert result["intent_type"] == IntentType.REFINE_PLAN

    def test_classifies_save_requests(self):
        from graph import intent_router

        messages = [
            "Save this project",
            "Keep this composition",
            "save",
            "keep it",
        ]
        for msg in messages:
            result = intent_router({"user_message": msg})
            assert result["intent_type"] == IntentType.SAVE_PROJECT

    def test_classifies_load_requests(self):
        from graph import intent_router

        messages = [
            "Load my project",
            "Open the last composition",
            "load",
            "open something",
        ]
        for msg in messages:
            result = intent_router({"user_message": msg})
            assert result["intent_type"] == IntentType.LOAD_REQUESTS

    def test_classifies_questions(self):
        from graph import intent_router

        messages = [
            "What key is the bridge in?",
            "How do I add a voice?",
            "Why is the tempo so slow?",
            "where is the melody",
        ]
        for msg in messages:
            result = intent_router({"user_message": msg})
            assert result["intent_type"] == IntentType.ANSWER_QUESTION

    def test_fallback_to_answer_question(self):
        from graph import intent_router

        # Unknown message should default to answer_question
        result = intent_router({"user_message": "xyz123"})
        assert result["intent_type"] == IntentType.ANSWER_QUESTION


# ── Test 2: Routing function ─────────────────────────────────────────


class TestRoutingFunction:
    """The routing function maps intent_type to node names."""

    def test_routes_new_sketch_to_creation(self):
        from graph import route_from_intent

        result = route_from_intent({"intent_type": IntentType.NEW_SKETCH})
        assert result == "new_sketch"

    def test_routes_plan_refine_to_refinement(self):
        from graph import route_from_intent

        result = route_from_intent({"intent_type": IntentType.REFINE_PLAN})
        assert result == "refine_plan"

    def test_routes_save_project_to_save(self):
        from graph import route_from_intent

        result = route_from_intent({"intent_type": IntentType.SAVE_PROJECT})
        assert result == "save_project"

    def test_routes_load_project_to_load(self):
        from graph import route_from_intent

        result = route_from_intent({"intent_type": IntentType.LOAD_REQUESTS})
        assert result == "load_requests"

    def test_routes_answer_question_to_answerer(self):
        from graph import route_from_intent

        result = route_from_intent({"intent_type": IntentType.ANSWER_QUESTION})
        assert result == "answer_question"


# ── Test 3: Graph structure ───────────────────────────────────────────


class TestGraphStructure:
    """The graph has the expected nodes and conditional edges."""

    def test_graph_has_intent_router(self):
        from graph.m2.graph_builder import build_music_graph

        app = build_music_graph()
        node_names = set(app.get_graph().nodes.keys())
        assert "intent_router" in node_names

    def test_graph_has_stub_destinations(self):
        from graph.m2.graph_builder import build_music_graph

        app = build_music_graph()
        node_names = set(app.get_graph().nodes.keys())
        expected_stubs = {
            "new_sketch",
            "refine_plan",
            "save_project",
            "load_requests",
            "answer_question",
        }
        assert expected_stubs.issubset(node_names)


# ── Test 4: End-to-end routing ───────────────────────────────────────


class TestEndToEndRouting:
    """Invoke the graph and verify it reaches the right destination."""

    def test_routes_creation_request(self):
        from graph.m2.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Write me a rock tune"})
        assert result.get("path") == "creation"

    def test_routes_refinement_request(self):
        from graph.m2.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Make the chorus busier"})
        assert result.get("path") == "refinement"

    def test_routes_save_request(self):
        from graph.m2.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Save this project"})
        assert result.get("path") == "save"

    def test_routes_load_request(self):
        from graph.m2.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "Load my project"})
        assert result.get("path") == "load"

    def test_routes_question(self):
        from graph.m2.graph_builder import build_music_graph

        app = build_music_graph()
        result = app.invoke({"user_message": "What key is the bridge in?"})
        assert result.get("path") == "answerer"
