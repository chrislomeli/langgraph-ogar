"""
Tests for the full OGAR pipeline (outer graph).

Black-box: invoke the compiled outer graph, assert on final state.
All tests use deterministic stubs (no LLM calls).
"""
import pytest

from ogar.runtime.graph import build_ogar_graph


def _invoke_ogar(pid="test_proj", **overrides):
    """Helper: build + invoke the full OGAR graph with default inputs."""
    graph = build_ogar_graph()
    inputs = {
        "pid": pid,
        "project": None,
        "stage": "",
        "questions": [],
        "human_reply": None,
        "patch": None,
        "validation_errors": [],
        "plan_steps": [],
        "current_step_index": 0,
        "tool_request": None,
        "tool_response": None,
        "tool_error": None,
        "retry_count": 0,
        "run_status": "running",
        "audit_log": [],
        "decision": "",
        **overrides,
    }
    return graph.invoke(inputs)


class TestOGARHappyPath:
    """Full pipeline: intake → planner → execute → finalize."""

    def test_reaches_done(self):
        out = _invoke_ogar()
        assert out["run_status"] == "done"

    def test_project_populated(self):
        out = _invoke_ogar()
        project = out["project"]
        assert project is not None
        assert project.title.strip() != ""
        assert len(project.goals) >= 1
        assert len(project.requirements) >= 1

    def test_plan_steps_all_done(self):
        out = _invoke_ogar()
        steps = out.get("plan_steps", [])
        assert len(steps) >= 1
        for s in steps:
            assert s["status"] == "done", f"Step {s['step_id']} not done: {s['status']}"

    def test_audit_log_has_events(self):
        out = _invoke_ogar()
        audit = out.get("audit_log", [])
        assert len(audit) >= 3  # at least: plan_proposed, some executions, finalized

    def test_audit_log_contains_orchestrator_events(self):
        out = _invoke_ogar()
        audit = out.get("audit_log", [])
        events = [e.get("event", "") for e in audit]
        assert any("orch_plan_proposed" in e for e in events)
        assert any("orch_plan_complete" in e for e in events)

    def test_audit_log_ends_with_finalized(self):
        out = _invoke_ogar()
        audit = out.get("audit_log", [])
        assert audit[-1]["event"] == "run_finalized"
        assert audit[-1]["status"] == "done"

    def test_decision_is_done(self):
        out = _invoke_ogar()
        assert out["decision"] == "done"


class TestOGARDecideRouting:
    """Test the decide node's routing logic in isolation."""

    def test_done_when_all_steps_complete(self):
        from ogar.runtime.graph.ogar_graph import decide

        state = {
            "plan_steps": [
                {"step_id": "s1", "status": "done"},
                {"step_id": "s2", "status": "done"},
            ],
            "current_step_index": 2,
            "tool_error": None,
            "retry_count": 0,
        }
        result = decide(state)
        assert result["decision"] == "done"

    def test_next_step_when_steps_remaining(self):
        from ogar.runtime.graph.ogar_graph import decide

        state = {
            "plan_steps": [
                {"step_id": "s1", "status": "done"},
                {"step_id": "s2", "status": "pending"},
            ],
            "current_step_index": 0,
            "tool_error": None,
            "retry_count": 0,
        }
        result = decide(state)
        assert result["decision"] == "next_step"

    def test_revise_plan_on_error(self):
        from ogar.runtime.graph.ogar_graph import decide

        state = {
            "plan_steps": [{"step_id": "s1", "status": "pending"}],
            "current_step_index": 0,
            "tool_error": "something broke",
            "retry_count": 0,
        }
        result = decide(state)
        assert result["decision"] == "revise_plan"

    def test_fail_on_error_with_retries_exhausted(self):
        from ogar.runtime.graph.ogar_graph import decide

        state = {
            "plan_steps": [{"step_id": "s1", "status": "pending"}],
            "current_step_index": 0,
            "tool_error": "still broken",
            "retry_count": 3,
        }
        result = decide(state)
        assert result["decision"] == "fail"
        assert result["run_status"] == "failed"

    def test_done_when_empty_plan(self):
        from ogar.runtime.graph.ogar_graph import decide

        state = {
            "plan_steps": [],
            "current_step_index": 0,
            "tool_error": None,
            "retry_count": 0,
        }
        result = decide(state)
        assert result["decision"] == "done"
