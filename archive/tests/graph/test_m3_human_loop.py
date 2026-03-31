"""
Milestone 3: Human-in-the-loop.

Tests verify:
  1. mock_planner produces a plan with expected structure
  2. Graph pauses at plan_review (interrupt)
  3. Resume with approval → stub_compiler runs
  4. Resume with rejection → loops back to engine
  5. State preserved across interrupt

The graph:
  START → mock_planner → plan_review (interrupt) → conditional
                ↑                                       │
                │            approved → stub_compiler    │
                └──────────  rejected ──────────────────┘
"""

from __future__ import annotations

from langgraph.types import Command


def _make_config():
    """Each test needs a unique thread_id so checkpointer state doesn't leak."""
    import uuid
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


# ── Test 1: Plan creation ───────────────────────────────────────────

class TestPlanCreation:
    """mock_planner should produce a plan with expected structure."""

    def test_plan_exists(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()
        result = app.invoke({"user_message": "Write me a rock tune"}, config)

        assert result["plan"] is not None, "mock_planner should produce a plan"

    def test_plan_has_expected_keys(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()
        result = app.invoke({"user_message": "Write me a rock tune"}, config)

        plan = result["plan"]
        assert "genre" in plan, "mock plan should include genre"
        assert "voices" in plan, "mock plan should include voices"


# ── Test 2: Approve continues forward ───────────────────────────────

class TestApprove:
    """Resuming with approved=True should reach stub_compiler."""

    def test_approve_reaches_compiler(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()

        # First invoke: runs mock_planner, then pauses at plan_review
        paused_result = app.invoke({"user_message": "Write me a rock tune"}, config)

        # Resume with approval
        result = app.invoke(Command(resume={"approved": True}), config)

        print("final")

        assert result.get("score_generated") is True, \
            "After approval, stub_compiler should set compiled=True"


    def test_funk_reaches_compiler(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()

        # First invoke: runs mock_planner, then pauses at plan_review
        paused_result = app.invoke({"user_message": "Write me a funk tune"}, config)

        # inspect the plan
        print("Plan to review:", paused_result["plan"])
        if paused_result["plan"]["genre"] == "Funk":
            print("Funk plan detected, proceeding with rejection")


        # Resume with approval
        result = app.invoke(Command(resume={"approved": False}), config)

        assert result.get("score_generated") is None, \
            "After approval, stub_compiler should set compiled=False for funk music"


# ── Test 3: Reject loops back ───────────────────────────────────────

class TestReject:
    """Resuming with approved=False should loop back to mock_planner."""

    def test_reject_loops_back_and_pauses_again(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()

        # First invoke: pauses at plan_review
        app.invoke({"user_message": "Write me a rock tune"}, config)

        # Reject: loops back to mock_planner, then pauses again
        second = app.invoke(Command(resume={"approved": False}), config)

        assert second["plan"] is not None, \
            "After rejection, mock_planner should produce a new plan"

    def test_reject_then_approve(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()

        # original request
        app.invoke({"user_message": "Write me a rock tune"}, config)

        # first interruption causes a loop back to mock_planner()
        app.invoke(Command(resume={"approved": False}), config)

        # mock engine does not do anything different, but it is 'wired' to plan_review - which again returns to this line - so we can reject the first, then accept the second
        result = app.invoke(Command(resume={"approved": True}), config)

        print("Reject-then-approve test completed")
        assert result.get("score_generated") is True, \
            "After reject-then-approve, stub_compiler should run"


# ── Test 4: State preserved ─────────────────────────────────────────

class TestStatePreserved:
    """State fields should survive across the interrupt."""

    def test_user_message_preserved(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()
        result = app.invoke({"user_message": "Write me a rock tune"}, config)

        assert result["user_message"] == "Write me a rock tune"

    def test_plan_survives_into_compiler(self):
        from graph.m3.graph_builder import build_music_graph

        app = build_music_graph()
        config = _make_config()

        paused = app.invoke({"user_message": "Write me a rock tune"}, config)
        plan_at_pause = paused["plan"]

        result = app.invoke(Command(resume={"approved": True}), config)

        assert result["plan"] == plan_at_pause, \
            "plan should be unchanged after approval and compilation"
